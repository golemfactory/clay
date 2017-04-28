from collections import deque
from ipaddress import AddressValueError
import logging
from pydispatch import dispatcher
import random
from threading import Lock
import time


from golem.core.simplechallenge import create_challenge, accept_challenge, solve_challenge
from golem.diag.service import DiagnosticsProvider
from golem.model import KnownHosts, MAX_STORED_HOSTS, db
from golem.network.p2p.peersession import PeerSession, PeerSessionInfo
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpnetwork import TCPNetwork, TCPConnectInfo, SocketAddress, SafeProtocol
from golem.network.transport.tcpserver import TCPServer, PendingConnectionsServer
from golem.ranking.manager.gossip_manager import GossipManager
from peerkeeper import PeerKeeper

logger = logging.getLogger(__name__)

LAST_MESSAGE_BUFFER_LEN = 5  # How many last messages should we keep
REFRESH_PEERS_TIMEOUT = 1200  # How often should we disconnect with a random node
RECONNECT_WITH_SEED_THRESHOLD = 30  # After how many seconds from the last try should we try to connect with seed?
SOLVE_CHALLENGE = True  # Should nodes that connects with us solve hashcash challenge?
BASE_DIFFICULTY = 5  # What should be a challenge difficulty?
HISTORY_LEN = 5  # How many entries from challenge history should we remember
TASK_INTERVAL = 10
PEERS_INTERVAL = 30

SEEDS = [('188.165.227.180', 40102), ('188.165.227.180', 40104), ('94.23.196.166', 40102), ('94.23.196.166', 40104)]


class P2PService(PendingConnectionsServer, DiagnosticsProvider):
    def __init__(self, node, config_desc, keys_auth, connect_to_known_hosts=True):
        """ Create new P2P Server. Listen on port for connections and connect to other peers. Keeps
        up-to-date list of peers information and optimal number of open connections.
        :param Node node: Information about this node
        :param ClientConfigDescriptor config_desc: configuration options
        :param KeysAuth keys_auth: authorization manager
        """
        network = TCPNetwork(ProtocolFactory(SafeProtocol, self, SessionFactory(PeerSession)), config_desc.use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)

        self.node = node
        self.keys_auth = keys_auth
        self.peer_keeper = PeerKeeper(keys_auth.get_key_id())
        self.task_server = None
        self.resource_server = None
        self.metadata_manager = None
        self.resource_port = 0
        self.suggested_address = {}
        self.suggested_conn_reverse = {}
        self.gossip_keeper = GossipManager()
        self.manager_session = None

        # Useful config options
        self.node_name = self.config_desc.node_name
        self.last_message_time_threshold = self.config_desc.p2p_session_timeout
        self.last_message_buffer_len = LAST_MESSAGE_BUFFER_LEN
        self.last_time_tried_connect_with_seed = 0
        self.reconnect_with_seed_threshold = RECONNECT_WITH_SEED_THRESHOLD
        self.refresh_peers_timeout = REFRESH_PEERS_TIMEOUT
        self.should_solve_challenge = SOLVE_CHALLENGE
        self.challenge_history = deque(maxlen=HISTORY_LEN)
        self.last_challenge = ""
        self.base_difficulty = BASE_DIFFICULTY
        self.connect_to_known_hosts = connect_to_known_hosts

        # Peers options
        self.peers = {}  # active peers
        self.peer_order = []  # peer connection order
        self.incoming_peers = {}  # known peers with connections
        self.free_peers = []  # peers to which we're not connected
        self.resource_peers = {}
        self.seeds = set()

        self._peer_lock = Lock()

        try:
            self.__remove_redundant_hosts_from_db()
            self.__sync_seeds()
        except Exception as exc:
            logger.error("Error reading seed addresses: {}".format(exc))

        # Timers
        self.last_peers_request = time.time()
        self.last_tasks_request = time.time()
        self.last_refresh_peers = time.time()

        self.last_messages = []

    def new_connection(self, session):
        session.start()

    def start_accepting(self, listening_established=None, listening_failure=None):
        def established(port):
            self.cur_port = port
            self.node.p2p_prv_port = port
            dispatcher.send(signal='golem.p2p', event='listening', port=port)
            logger.debug('accepting established %r', self.cur_port)

        super(P2PService, self).start_accepting(listening_established=established)

    def connect_to_network(self):
        self.connect_to_seeds()
        if not self.connect_to_known_hosts:
            return

        for host in KnownHosts.select().where(KnownHosts.is_seed == False):  # noqa
            ip_address = host.ip_address
            port = host.port

            logger.debug("Connecting to {}:{}".format(ip_address, port))
            try:
                socket_address = SocketAddress(ip_address, port)
                self.connect(socket_address)
            except Exception as exc:
                logger.error("Cannot connect to host {}:{}: {}"
                             .format(ip_address, port, exc))

    def connect_to_seeds(self):
        self.last_time_tried_connect_with_seed = time.time()
        if not self.connect_to_known_hosts:
            return

        for ip_address, port in self.seeds:
            try:
                socket_address = SocketAddress(ip_address, port)
                self.connect(socket_address)
            except Exception as exc:
                logger.error("Cannot connect to seed {}:{}: {}"
                             .format(ip_address, port, exc))

    def connect(self, socket_address):
        connect_info = TCPConnectInfo([socket_address], self.__connection_established,
                                      P2PService.__connection_failure)
        self.network.connect(connect_info)

    def add_known_peer(self, node, ip_address, port):
        is_seed = node.is_super_node() if node else False

        try:
            with db.transaction():
                KnownHosts.delete().where(
                    (KnownHosts.ip_address == ip_address) & (KnownHosts.port == port)
                ).execute()

                KnownHosts.insert(
                    ip_address=ip_address,
                    port=port,
                    last_connected=time.time(),
                    is_seed=is_seed
                ).execute()

            self.__remove_redundant_hosts_from_db()
            self.__sync_seeds()

        except Exception as err:
            logger.error("Couldn't add known peer {}:{} : {}".format(ip_address, port, err))

    def set_metadata_manager(self, metadata_manager):
        self.metadata_manager = metadata_manager

    def interpret_metadata(self, *args, **kwargs):
        self.metadata_manager.interpret_metadata(*args, **kwargs)

    def sync_network(self):
        """ Get information about new tasks and new peers in the network. Remove excess information
        about peers
        """
        if self.task_server:
            self.__send_message_get_tasks()

        if time.time() - self.last_peers_request > PEERS_INTERVAL:
            self.last_peers_request = time.time()
            self.__sync_free_peers()
            self.__sync_peer_keeper()
            self.__send_get_peers()

        self.__remove_old_peers()
        self._sync_pending()
        if len(self.peers) == 0:
            if time.time() - self.last_time_tried_connect_with_seed > self.reconnect_with_seed_threshold:
                self.connect_to_seeds()

    def get_diagnostics(self, output_format):
        peer_data = []
        for peer in self.peers.values():
            peer = PeerSessionInfo(peer).get_simplified_repr()
            peer_data.append(peer)
        return self._format_diagnostics(peer_data, output_format)

    def ping_peers(self, interval):
        """ Send ping to all peers with whom this peer has open connection
        :param int interval: will send ping only if time from last ping was longer than interval
        """
        for p in self.peers.values():
            p.ping(interval)

    def find_peer(self, key_id):
        """ Find peer with given id on list of active connections
        :param key_id: id of a searched peer
        :return None|PeerSession: connection to a given peer or None
        """
        return self.peers.get(key_id)

    def get_peers(self):
        """ Return all open connection to other peers that this node keeps
        :return dict: dictionary of peers sessions
        """
        return self.peers

    def get_seeds(self):
        """ Return all known seed peers
        :return dict: a list of (address, port) tuples
        """
        return self.seeds

    def add_peer(self, key_id, peer):
        """ Add a new open connection with a peer to the list of peers
        :param str key_id: peer id
        :param PeerSession peer: peer session with given peer
        """
        logger.info("Adding peer {}, key id difficulty: {}".format(key_id, self.keys_auth.get_difficulty(peer.key_id)))
        with self._peer_lock:
            self.peers[key_id] = peer
            self.peer_order.append(key_id)
        self.__send_degree()

    def add_to_peer_keeper(self, peer_info):
        """ Add information about peer to the peer keeper
        :param Node peer_info: information about new peer
        """
        peer_to_ping_info = self.peer_keeper.add_peer(peer_info)
        if peer_to_ping_info and peer_to_ping_info.key in self.peers:
            peer_to_ping = self.peers[peer_to_ping_info.key]
            if peer_to_ping:
                peer_to_ping.ping(0)

    def pong_received(self, key_num):
        """ React to pong received from other node
        :param key_num: public key of a ping sender
        :return:
        """
        self.peer_keeper.pong_received(key_num)

    def try_to_add_peer(self, peer_info, force=False):
        """ Add peer to inner peer information
        :param dict peer_info: dictionary with information about peer
        :param force: add or overwrite existing data
        """
        key_id = peer_info["node"].key
        if force or self.__is_new_peer(key_id):
            logger.info("add peer to incoming {} {} {} ({})".format(peer_info["node_name"],
                                                                    peer_info["address"],
                                                                    peer_info["port"],
                                                                    key_id))

            self.incoming_peers[key_id] = {"address": peer_info["address"],
                                           "port": peer_info["port"],
                                           "node": peer_info["node"],
                                           "node_name": peer_info["node_name"],
                                           "conn_trials": 0}
            if key_id not in self.free_peers:
                self.free_peers.append(key_id)
            logger.debug(self.incoming_peers)

    def remove_peer(self, peer_session):
        """ Remove given peer session
        :param PeerSession peer_session: remove peer session
        """
        self.remove_pending_conn(peer_session.conn_id)

        peer_id = peer_session.key_id
        stored_session = self.peers.get(peer_id)

        if stored_session == peer_session:
            self.remove_peer_by_id(peer_id)

    def remove_peer_by_id(self, peer_id):
        """ Remove peer session with peer that has given id
        :param str peer_id:
        """
        with self._peer_lock:
            peer = self.peers.pop(peer_id, None)
            self.incoming_peers.pop(peer_id, None)
            self.suggested_address.pop(peer_id, None)
            self.suggested_conn_reverse.pop(peer_id, None)

            if peer_id in self.free_peers:
                self.free_peers.remove(peer_id)
            if peer_id in self.peer_order:
                self.peer_order.remove(peer_id)

        if peer:
            self.__send_degree()
        else:
            logger.info("Can't remove peer {}, unknown peer".format(peer_id))

    def refresh_peer(self, peer):
        self.remove_peer(peer)
        self.try_to_add_peer({"address": peer.address,
                              "port": peer.port,
                              "node": peer.node_info,
                              "node_name": peer.node_name},
                             force=True)

    def enough_peers(self):
        """ Inform whether peer has optimal or more open connections with other peers
        :return bool: True if peer has enough open connections with other peers, False otherwise
        """
        with self._peer_lock:
            return len(self.peers) >= self.config_desc.opt_peer_num

    def set_last_message(self, type_, client_key_id, t, msg, address, port):
        """ Add given message to last message buffer and inform peer keeper about it
        :param int type_: message time
        :param client_key_id: public key of a message sender
        :param float t: time of receiving message
        :param Message msg: received message
        :param str address: sender address
        :param int port: sender port
        """
        self.peer_keeper.set_last_message_time(client_key_id)
        if len(self.last_messages) >= self.last_message_buffer_len:
            self.last_messages = self.last_messages[-(self.last_message_buffer_len - 1):]

        self.last_messages.append([type_, t, address, port, msg])

    def get_last_messages(self):
        """ Return list of a few recent messages
        :return list: last messages
        """
        return self.last_messages

    def manager_session_disconnect(self, uid):
        """ Remove manager session
        """
        self.manager_session = None

    def change_config(self, config_desc):
        """ Change configuration descriptor.
        If node_name was changed, send hello to all peers to update node_name.
        If listening port is changed, than stop listening on old port and start
        listening on a new one. If seed address is changed, connect to a new seed.
        Change configuration for resource server.
        :param ClientConfigDescriptor config_desc: new config descriptor
        """

        is_node_name_changed = self.node_name != config_desc.node_name

        TCPServer.change_config(self, config_desc)
        self.node_name = config_desc.node_name

        self.last_message_time_threshold = self.config_desc.p2p_session_timeout

        if is_node_name_changed:
            for peer in self.peers.values():
                peer.hello()

        for peer in self.peers.values():
            if peer.port == self.config_desc.seed_port and peer.address == self.config_desc.seed_host:
                return

        try:
            socket_address = SocketAddress(self.config_desc.seed_host, self.config_desc.seed_port)
            self.connect(socket_address)
        except AddressValueError as err:
            logger.error('Invalid seed address: ' + str(err))

        if self.resource_server:
            self.resource_server.change_config(config_desc)

    def change_address(self, th_dict_repr):
        """ Change peer address in task header dictionary representation
        :param dict th_dict_repr: task header dictionary representation that should be changed
        """
        try:
            id_ = th_dict_repr["task_owner_key_id"]

            if self.peers[id_]:
                th_dict_repr["address"] = self.peers[id_].address
                th_dict_repr["port"] = self.peers[id_].port
        except KeyError as err:
            logger.error("Wrong task representation: {}".format(err))

    def check_solution(self, solution, challenge, difficulty):
        """
        Check whether solution is valid for given challenge and it's difficulty
        :param str solution: solution to check
        :param str challenge: solved puzzle
        :param int difficulty: difficulty of a challenge
        :return boolean: true if challenge has been correctly solved, false otherwise
        """
        return accept_challenge(challenge, solution, difficulty)

    def solve_challenge(self, key_id, challenge, difficulty):
        """ Solve challenge with given difficulty for a node with key_id
        :param str key_id: key id of a node that has send this challenge
        :param str challenge: puzzle to solve
        :param int difficulty: difficulty of challenge
        :return str: solution of a challenge
        """
        self.challenge_history.append([key_id, challenge])
        solution, time_ = solve_challenge(challenge, difficulty)
        logger.debug("Solved challenge with difficulty {} in {} sec".format(difficulty, time_))
        return solution

    def get_peers_degree(self):
        """ Return peers degree level
        :return dict: dictionary where peers ids are keys and their degrees are values
        """
        return {peer.key_id: peer.degree for peer in self.peers.values()}

    def get_key_id(self):
        """ Return node public key in a form of an id """
        return self.peer_keeper.key_num

    def key_changed(self):
        """ React to the fact that key id has been changed. Drop all connections with peer,
        restart peer keeper and connect to the network with new key id.
        """
        self.peer_keeper.restart(self.keys_auth.get_key_id())
        for p in self.peers.values():
            p.dropped()

        try:
            socket_address = SocketAddress(self.config_desc.seed_host, self.config_desc.seed_port)
            self.connect(socket_address)
        except AddressValueError, err:
            logger.error("Invalid seed address: " + err.message)

    def encrypt(self, data, public_key):
        """ Encrypt data with given public_key. If no public_key is given, or it's equal to zero
         return data
        :param str data: data that should be encrypted
        :param public_key: public key that should be used to encrypt the data
        :return str: encrypted data (or data if no public key was given)
        """
        if public_key == 0 or public_key is None:
            return data
        return self.keys_auth.encrypt(data, public_key)

    def decrypt(self, data):
        """ Decrypt given data
        :param str data: encrypted data
        :return str: data decrypted with private key
        """
        return self.keys_auth.decrypt(data)

    def sign(self, data):
        """ Sign given data with private key
        :param str data: data to be signed
        :return str: data signed with private key
        """
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        """ Verify the validity of signature
        :param str sig: signature
        :param str data: expected data
        :param public_key: public key that should be used to verify signed data.
        :return bool: verification result
        """
        return self.keys_auth.verify(sig, data, public_key)

    def set_suggested_address(self, client_key_id, addr, port):
        """ Set suggested address for peer. This node will be used as first for connection attempt
        :param str client_key_id: peer public key
        :param str addr: peer suggested address
        :param int port: peer suggested port [this argument is ignored right now]
        :return:
        """
        self.suggested_address[client_key_id] = addr

    def get_suggested_conn_reverse(self, client_key_id):
        return self.suggested_conn_reverse.get(client_key_id, False)

    def set_suggested_conn_reverse(self, client_key_id, value=True):
        self.suggested_conn_reverse[client_key_id] = value

    def get_socket_addresses(self, node_info, port, key_id):
        """ Change node info into tcp addresses. Add suggested address
        :param Node node_info: node information
        :param int port: port that should be used
        :param key_id: node's public key
        :return:
        """
        socket_addresses = PendingConnectionsServer.get_socket_addresses(self, node_info, port, key_id)
        addr = self.suggested_address.get(key_id, None)
        if addr:
            socket_addresses = [SocketAddress(addr, port)] + socket_addresses
        return socket_addresses

    # Kademlia functions
    #############################
    def send_find_nodes(self, peers_to_find):
        """ Kademlia find node function. Send find node request to the closest neighbours
         of a sought node
        :param dict peers_to_find: list of nodes that should be find with their closest neighbours list
        """
        for node_key_id, neighbours in peers_to_find.iteritems():
            for neighbour in neighbours:
                peer = self.peers.get(neighbour.key)
                if peer:
                    peer.send_find_node(node_key_id)

    # Find node
    #############################
    def find_node(self, node_key_id):
        """ Kademlia find node function. Find closest neighbours of a node with given public key
        :param node_key_id: public key of a sought node
        :return list: list of information about closest neighbours
        """
        neighbours = self.peer_keeper.neighbours(node_key_id)
        peer_infos = []
        for peer in neighbours:
            peer_infos.append({"address": peer.prv_addr,
                               "port": peer.prv_port,
                               "id": peer.key,
                               "node": peer,
                               "node_name": peer.node_name})
        return peer_infos

    # Resource functions
    #############################
    def set_resource_server(self, resource_server):
        """ Set resource server
        :param BaseResourceServer resource_server: resource server instance
        """
        self.resource_server = resource_server

    def set_resource_peer(self, addr, port):
        """Set resource server port and add it to resource peers set
        :param str addr: address of resource server
        :param int port: resource server listen port
        """
        self.resource_port = port
        self.resource_peers[self.keys_auth.get_key_id()] = [addr, port, self.node_name, self.node]

    def send_get_resource_peers(self):
        """ Request information about resource peers from peers"""
        for p in self.peers.values():
            p.send_get_resource_peers()

    def get_resource_peers(self):
        """ Prepare information about resource peers
        :return list: list of resource peers information
        """
        resource_peers_info = []
        resource_peers = dict(self.resource_peers)
        for key_id, [addr, port, node_name, node_info] in resource_peers.iteritems():
            resource_peers_info.append({'node_name': node_name, 'addr': addr, 'port': port, 'key_id': key_id,
                                        'node': node_info})

        return resource_peers_info

    def set_resource_peers(self, resource_peers):
        """ Add new resource peers information to resource server
        :param dict resource_peers: dictionary resource peers known by
        :return:
        """
        for peer in resource_peers:
            try:
                if peer['key_id'] != self.keys_auth.get_key_id():
                    self.resource_peers[peer['key_id']] = [peer['addr'], peer['port'], peer['node_name'], peer['node']]
            except KeyError as err:
                logger.error("Wrong set peer message (peer: {}): {}".format(peer, str(err)))
        resource_peers_copy = self.resource_peers.copy()
        if self.get_key_id() in resource_peers_copy:
            del resource_peers_copy[self.node_name]
        self.resource_server.set_resource_peers(resource_peers_copy)

    # TASK FUNCTIONS
    ############################
    def get_tasks_headers(self):
        """ Return a list of a known tasks headers
        :return list: list of task header
        """
        return self.task_server.get_tasks_headers()

    def add_task_header(self, th_dict_repr):
        """ Add new task header to a list of known task headers
        :param dict th_dict_repr: new task header dictionary representation
        :return bool: True if a task header was in a right format, False otherwise
        """
        return self.task_server.add_task_header(th_dict_repr)

    def remove_task_header(self, task_id):
        """ Remove header of a task with given id from a list of a known tasks
        :param str task_id: id of a task that should be removed
        """
        self.task_server.remove_task_header(task_id)

    def remove_task(self, task_id):
        """ Ask all peers to remove information about given task
        :param str task_id: id of a task that should be removed
        """
        for p in self.peers.values():
            p.send_remove_task(task_id)

    def want_to_start_task_session(self, key_id, node_info, conn_id, super_node_info=None):
        """ Inform peer with public key <key_id> that node from node info want to start task session with him. If
        peer with given id is on a list of peers that this message will be send directly. Otherwise all peers will
        receive a request to pass this message.
        :param str key_id: key id of a node that should open a task session
        :param Node node_info: information about node that requested session
        :param str conn_id: connection id for reference
        :param Node|None super_node_info: *Default: None* information about node with public ip that took part
        in message transport
        """
        if not self.task_server.task_connections_helper.is_new_conn_request(
                conn_id, key_id, node_info, super_node_info):
            # fixme
            self.task_server.remove_pending_conn(conn_id)
            self.task_server.remove_responses(conn_id)
            return

        if super_node_info is None and self.node.is_super_node():
            super_node_info = self.node

        logger.debug("Try to start task session {}".format(key_id))

        connected_peer = self.peers.get(key_id)
        if connected_peer:
            if node_info.key == self.node.key:
                self.set_suggested_conn_reverse(key_id)
            connected_peer.send_want_to_start_task_session(node_info, conn_id, super_node_info)
            return

        msg_snd = False

        for peer in self.peers.values():
            if peer.key_id != node_info.key:
                peer.send_set_task_session(key_id, node_info, conn_id, super_node_info)
                msg_snd = True

        if msg_snd and node_info.key == self.node.key:
            self.task_server.add_forwarded_session_request(key_id, conn_id)

        # TODO This method should be only sent to supernodes or nodes that are closer to the target node

        if not msg_snd and node_info.key == self.get_key_id():
            self.task_server.task_connections_helper.cannot_start_task_session(conn_id)

    def inform_about_task_nat_hole(self, key_id, rv_key_id, addr, port, ans_conn_id):
        """
        :param key_id:
        :param rv_key_id:
        :param addr:
        :param port:
        :param ans_conn_id:
        :return:
        """
        logger.debug("Nat hole ready {}:{}".format(addr, port))
        peer = self.peers.get(key_id)
        if peer:
            peer.send_task_nat_hole(rv_key_id, addr, port, ans_conn_id)

    def traverse_nat(self, key_id, addr, port, conn_id, super_key_id):
        self.task_server.traverse_nat(key_id, addr, port, conn_id, super_key_id)

    def inform_about_nat_traverse_failure(self, key_id, res_key_id, conn_id):
        peer = self.peers.get(key_id)
        if peer:
            peer.send_inform_about_nat_traverse_failure(res_key_id, conn_id)

    def send_nat_traverse_failure(self, key_id, conn_id):
        peer = self.peers.get(key_id)
        if peer:
            peer.send_nat_traverse_failure(conn_id)

    def traverse_nat_failure(self, conn_id):
        self.task_server.traverse_nat_failure(conn_id)

    def peer_want_task_session(self, node_info, super_node_info, conn_id):
        """ Process request to start task session from this node to a node from node_info.
        :param Node node_info: node that requests task session with this node
        :param Node|None super_node_info: information about supernode that has passed this information
        :param conn_id: connection id
        """
        # self.task_server.task_connections_helper.want_to_start(conn_id, node_info, super_node_info)
        self.task_server.start_task_session(node_info, super_node_info, conn_id)

    #############################
    # RANKING FUNCTIONS         #
    #############################
    def send_gossip(self, gossip, send_to):
        """ send gossip to given peers
        :param list gossip: list of gossips that should be sent
        :param list send_to: list of ids of peers that should receive gossip
        """
        for peer_id in send_to:
            peer = self.find_peer(peer_id)
            if peer is not None:
                peer.send_gossip(gossip)

    def hear_gossip(self, gossip):
        """ Add newly heard gossip to the gossip list
        :param list gossip: list of gossips from one peer
        """
        self.gossip_keeper.add_gossip(gossip)

    def pop_gossips(self):
        """ Return all gathered gossips and clear gossip buffer
        :return list: list of all gossips
        """
        return self.gossip_keeper.pop_gossips()

    def send_stop_gossip(self):
        """ Send stop gossip message to all peers
        """
        for peer in self.peers.values():
            peer.send_stop_gossip()

    def stop_gossip(self, id_):
        """ Register that peer with given id has stopped gossiping
        :param str id_: id of a string that has stopped gossiping
        """
        self.gossip_keeper.register_that_peer_stopped_gossiping(id_)

    def pop_stop_gossip_form_peers(self):
        """ Return set of all peers that has stopped gossiping
        :return set: set of peers id's
        """
        return self.gossip_keeper.pop_peers_that_stopped_gossiping()

    def push_local_rank(self, node_id, loc_rank):
        """ Send local rank to peers
        :param str node_id: id of anode that this opinion is about
        :param list loc_rank: opinion about this node
        :return:
        """
        for peer in self.peers.values():
            peer.send_loc_rank(node_id, loc_rank)

    def safe_neighbour_loc_rank(self, neigh_id, about_id, rank):
        """
        Add local rank from neighbour to the collection
        :param str neigh_id: id of a neighbour - opinion giver
        :param str about_id: opinion is about a node with this id
        :param list rank: opinion that node <neigh_id> have about node <about_id>
        :return:
        """
        self.gossip_keeper.add_neighbour_loc_rank(neigh_id, about_id, rank)

    def pop_neighbours_loc_ranks(self):
        """ Return all local ranks that was collected in that round and clear the rank list
        :return list: list of all neighbours local rank sent to this node
        """
        return self.gossip_keeper.pop_neighbour_loc_ranks()

    def _set_conn_established(self):
        self.conn_established_for_type.update({
            P2PConnTypes.Start: self.__connection_established
        })

    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            P2PConnTypes.Start: P2PService.__connection_failure
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            P2PConnTypes.Start: P2PService.__connection_final_failure
        })

    # In the future it may be changed to something more flexible and more connected with key_id
    def _get_difficulty(self, key_id):
        return self.base_difficulty

    def _get_challenge(self, key_id):
        self.last_challenge = create_challenge(self.challenge_history, self.last_challenge)
        return self.last_challenge

    #############################
    # PRIVATE SECTION
    #############################

    def __send_get_peers(self):
        for p in self.peers.values():
            p.send_get_peers()

    def __send_message_get_tasks(self):
        if time.time() - self.last_tasks_request > TASK_INTERVAL:
            self.last_tasks_request = time.time()
            for p in self.peers.values():
                p.send_get_tasks()

    def __connection_established(self, session, conn_id=None):
        peer_conn = session.conn.transport.getPeer()
        ip_address = peer_conn.host
        port = peer_conn.port

        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)

        logger.debug("Connection to peer established. {}: {}, conn_id {}"
                     .format(ip_address, port, conn_id))

    @staticmethod
    def __connection_failure(conn_id=None):
        logger.info("Connection to peer failure {}.".format(conn_id))

    @staticmethod
    def __connection_final_failure(conn_id=None):
        logger.info("Can't connect to peer {}.".format(conn_id))

    def __is_new_peer(self, id_):
        return id_ not in self.incoming_peers and not self.__is_connected_peer(id_)

    def __is_connected_peer(self, id_):
        return id_ in self.peers or long(id_, 16) == self.get_key_id()

    def __remove_old_peers(self):
        for peer in self.peers.values():
            if time.time() - peer.last_message_time > self.last_message_time_threshold:
                self.remove_peer(peer)
                peer.disconnect(PeerSession.DCRTimeout)

    def __refresh_old_peers(self):
        cur_time = time.time()
        if cur_time - self.last_refresh_peers > self.refresh_peers_timeout:
            self.last_refresh_peers = cur_time
            if len(self.peers) > 1:
                peer_id = random.choice(self.peers.keys())
                peer = self.peers[peer_id]
                self.refresh_peer(peer)
                peer.disconnect(PeerSession.DCRRefresh)

    # TODO: throttle the tx rate of MessageDegree
    def __send_degree(self):
        degree = len(self.peers)
        for p in self.peers.values():
            p.send_degree(degree)

    def __sync_free_peers(self):
        while self.free_peers and not self.enough_peers():

            peer_id = random.choice(self.free_peers)
            self.free_peers.remove(peer_id)

            if not self.__is_connected_peer(peer_id):
                peer = self.incoming_peers[peer_id]
                node = peer['node']

                if peer['address'] == node.pub_addr:
                    port = node.p2p_pub_port or node.p2p_prv_port
                else:
                    port = node.p2p_prv_port

                logger.info("Connecting to peer {}:{}".format(peer['address'], port))
                self.incoming_peers[peer_id]["conn_trials"] += 1  # increment connection trials
                self._add_pending_request(P2PConnTypes.Start, node, port, node.key, args={})

    def __sync_peer_keeper(self):
        self.__remove_sessions_to_end_from_peer_keeper()
        peers_to_find = self.peer_keeper.sync()
        self.__remove_sessions_to_end_from_peer_keeper()
        if peers_to_find:
            self.send_find_nodes(peers_to_find)

    def __sync_seeds(self, known_hosts=None):
        if not known_hosts:
            known_hosts = KnownHosts.select().where(KnownHosts.is_seed)

        self.seeds = {(x.ip_address, x.port) for x in known_hosts if x.is_seed}
        self.seeds.update(SEEDS)

        ip_address = self.config_desc.seed_host
        port = self.config_desc.seed_port
        if ip_address and port:
            self.seeds.add((ip_address, port))

    def __remove_sessions_to_end_from_peer_keeper(self):
        for peer_id in self.peer_keeper.sessions_to_end:
            self.remove_peer_by_id(peer_id)
        self.peer_keeper.sessions_to_end = []

    @staticmethod
    def __remove_redundant_hosts_from_db():
        to_delete = KnownHosts.select() \
            .order_by(KnownHosts.last_connected.desc()) \
            .offset(MAX_STORED_HOSTS)
        KnownHosts.delete() \
            .where(KnownHosts.id << to_delete) \
            .execute()


class P2PConnTypes(object):
    """ P2P Connection Types that allows to choose right reaction  """
    Start = 1
