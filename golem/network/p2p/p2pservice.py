import logging
import random
import time

from ipaddress import AddressValueError

from golem.core.simplechallenge import create_challenge, accept_challenge, solve_challenge
from golem.network.p2p.peersession import PeerSession
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpnetwork import TCPNetwork, TCPConnectInfo, SocketAddress, SafeProtocol
from golem.network.transport.tcpserver import TCPServer, PendingConnectionsServer, PenConnStatus
from golem.ranking.gossipkeeper import GossipKeeper
from golem.task.taskconnectionshelper import TaskConnectionsHelper
from peerkeeper import PeerKeeper

logger = logging.getLogger(__name__)

LAST_MESSAGE_BUFFER_LEN = 5  # How many last messages should we keep
REFRESH_PEERS_TIMEOUT = 1200  # How often should we disconnect with a random node
SOLVE_CHALLENGE = True  # Should nodes that connects with us solve hashcash challenge?
BASE_DIFFICULTY = 5  # What should be a challenge difficulty?


class P2PService(PendingConnectionsServer):
    def __init__(self, node, config_desc, keys_auth):
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
        self.task_connections_helper = TaskConnectionsHelper()
        self.task_server = None
        self.resource_server = None
        self.resource_port = 0
        self.suggested_address = {}
        self.gossip_keeper = GossipKeeper()
        self.manager_session = None

        # Useful config options
        self.node_name = self.config_desc.node_name
        self.last_message_time_threshold = self.config_desc.p2p_session_timeout
        self.last_message_buffer_len = LAST_MESSAGE_BUFFER_LEN
        self.refresh_peers_timeout = REFRESH_PEERS_TIMEOUT
        self.should_solve_challenge = SOLVE_CHALLENGE
        self.challenge_history = []
        self.last_challenge = ""
        self.base_difficulty = BASE_DIFFICULTY

        # TODO: all peers powinno zostac przeniesione do peer keepera
        # Peers options
        self.peers = {}  # active peers
        self.peer_order = []  # peer connection order
        self.incoming_peers = {}  # known peers with connections
        self.free_peers = []  # peers to which we're not connected
        self.resource_peers = {}

        # Timers
        self.last_peers_request = time.time()
        self.last_tasks_request = time.time()
        self.last_refresh_peers = time.time()

        self.last_messages = []

        self.connect_to_network()

    def new_connection(self, session):
        session.start()

    def connect_to_network(self):
        """ Start listening on the port from configuration and try to connect to the seed node """
        self.start_accepting(listening_established=self._listening_established)
        try:
            socket_address = SocketAddress(self.config_desc.seed_host, self.config_desc.seed_port)
            self.connect(socket_address)
        except AddressValueError, err:
            logger.error("Invalid seed address: " + err.message)

    def _listening_established(self, port):
        self.cur_port = port
        self.node.p2p_prv_port = port

    def connect(self, socket_address):
        connect_info = TCPConnectInfo([socket_address], self.__connection_established,
                                      P2PService.__connection_failure)
        self.network.connect(connect_info)

    def set_task_server(self, task_server):
        """ Set task server
        :param TaskServer task_server: task server instance
        """
        self.task_server = task_server
        self.task_connections_helper.task_server = task_server

    def sync_network(self):
        """ Get information about new tasks and new peers in the network. Remove excess information
        about peers
        """
        if self.task_server:
            self.__send_message_get_tasks()

        self.__sync_free_peers()
        self.__remove_old_peers()
        self.__sync_peer_keeper()
        self._sync_pending()
        self.task_connections_helper.sync()

        self.__send_get_peers()

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

    def add_peer(self, key_id, peer):
        """ Add a new open connection with a peer to the list of peers
        :param str key_id: peer id
        :param PeerSession peer: peer session with given peer
        """
        logger.info("Adding peer {}, key id difficulty: {}".format(key_id, self.keys_auth.get_difficulty(peer.key_id)))
        self.peers[key_id] = peer
        self.peer_order.append(peer.key_id)
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
            logger.info("add peer to incoming {} {} {}".format(peer_info["node_name"],
                                                               peer_info["address"],
                                                               peer_info["port"]))

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
        pc = self.pending_connections.get(peer_session.conn_id)
        if pc:
            pc.status = PenConnStatus.Failure
            self._remove_pending_sockets(pc)

        for p in self.peers.keys():
            if self.peers[p] == peer_session:
                del self.peers[p]
                self.peer_order.remove(p)
                self.suggested_address.pop(p, None)
                break

        self.__send_degree()

    def remove_peer_by_id(self, peer_id):
        """ Remove peer session with peer that has given id
        :param str peer_id:
        """
        peer = self.peers.get(peer_id)
        if not peer:
            logger.info("Can't remove peer {}, unknown peer".format(peer_id))
            return
        del self.peers[peer_id]
        self.peer_order.remove(peer_id)

        self.__send_degree()

    def refresh_peer(self, peer):
        # peer_id = peer.key_id
        # if peer_id in self.free_peers:
        #     self.free_peers.pop(peer_id)
        # self.incoming_peers.pop(peer_id, None)

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
        return len(self.peers) >= self.config_desc.opt_peer_num

    def redundant_peers(self):
        if self.enough_peers():
            start_idx = self.config_desc.opt_peer_num - 1
            return self.peer_order[start_idx:]
        return []

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
        """ Change configuration descriptor. If listening port is changed, than stop listening on old port and start
        listening on a new one. If seed address is changed, connect to a new seed.
        Change configuration for resource server.
        :param ClientConfigDescriptor config_desc: new config descriptor
        """

        TCPServer.change_config(self, config_desc)

        self.last_message_time_threshold = self.config_desc.p2p_session_timeout

        for peer in self.peers.values():
            if (peer.port == self.config_desc.seed_port) and (peer.address == self.config_desc.seed_host):
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

    def get_listen_params(self, key_id, rand_val):
        """ Return parameters that are needed for listen function in tuple
        :param str|None key_id: key id of a node with whom we want to connect
        :param int rand_val: session random value
        :return (int, str, str, Node, int, bool) | (int, str, str, Node, int, bool, str, int) : this node listen port,
        this node id, this node public key, information about this node, random value, information whether
        other node should solve cryptographic challenge, (optional: cryptographic challenge),
        (optional: cryptographic challenge difficulty)
        """
        if key_id:
            should_solve_challenge = self.should_solve_challenge
        else:
            should_solve_challenge = False
        listen_params = (self.cur_port, self.node_name, self.keys_auth.get_key_id(), self.node, rand_val,
                         should_solve_challenge)
        if should_solve_challenge:
            listen_params += (self._get_challenge(key_id), self._get_difficulty(key_id))

        return listen_params

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

    def get_socket_addresses(self, node_info, port, key_id):
        """ Change node info into tcp addresses. Add suggested address
        :param Node node_info: node information
        :param int port: port that should be used
        :param key_id: node's public key
        :return:
        """
        socket_addresses = PendingConnectionsServer.get_socket_addresses(self, node_info, port, key_id)
        addr = self.suggested_address.get(key_id)
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
        :param ResourceServer resource_server: resource server instance
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
        for key_id, [addr, port, node_name, node_info] in self.resource_peers.iteritems():
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
        if not self.task_connections_helper.is_new_conn_request(conn_id, key_id, node_info, super_node_info):
            return

        if super_node_info is None and self.node.is_super_node():
            super_node_info = self.node

        logger.debug("Try to start task session {}".format(key_id))
        msg_snd = False
        for peer in self.peers.itervalues():
            if peer.key_id == key_id:
                peer.send_want_to_start_task_session(node_info, conn_id, super_node_info)
                return

        for peer in self.peers.itervalues():
            if peer.key_id != node_info.key:
                peer.send_set_task_session(key_id, node_info, conn_id, super_node_info)
                msg_snd = True

        # TODO Tylko do wierzcholkow blizej supernode'ow / blizszych / lepszych wzgledem topologii sieci

        if not msg_snd and node_info.key == self.get_key_id():
            self.task_connections_helper.final_conn_failure(conn_id)

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
        for peer in self.peers.itervalues():
            if peer.key_id == key_id:
                peer.send_task_nat_hole(rv_key_id, addr, port, ans_conn_id)
                return

    def traverse_nat(self, key_id, addr, port, conn_id, super_key_id):
        self.task_server.traverse_nat(key_id, addr, port, conn_id, super_key_id)

    def inform_about_nat_traverse_failure(self, key_id, res_key_id, conn_id):
        for peer in self.peers.itervalues():
            if peer.key_id == key_id:
                peer.send_inform_about_nat_traverse_failure(res_key_id, conn_id)
                # TODO CO jak juz nie ma polaczenia?

    def send_nat_traverse_failure(self, key_id, conn_id):
        for peer in self.peers.itervalues():
            if peer.key_id == key_id:
                peer.send_nat_traverse_failure(conn_id)
                # TODO Co jak nie ma tego polaczenia

    def traverse_nat_failure(self, conn_id):
        self.task_server.traverse_nat_failure(conn_id)

    def peer_want_task_session(self, node_info, super_node_info, conn_id):
        """ Process request to start task session from this node to a node from node_info.
        :param Node node_info: node that requests task session with this node
        :param Node|None super_node_info: information about supernode that has passed this information
        :param conn_id: connection id
        """
        self.task_connections_helper.want_to_start(conn_id, node_info, super_node_info)

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

    def pop_gossip(self):
        """ Return all gathered gossips and clear gossip buffer
        :return list: list of all gossips
        """
        return self.gossip_keeper.pop_gossip()

    def send_stop_gossip(self):
        """ Send stop gossip message to all peers
        """
        for peer in self.peers.values():
            peer.send_stop_gossip()

    def stop_gossip(self, id_):
        """ Register that peer with given id has stopped gossiping
        :param str id_: id of a string that has stopped gossiping
        """
        self.gossip_keeper.stop_gossip(id_)

    def pop_stop_gossip_form_peers(self):
        """ Return set of all peers that has stopped gossiping
        :return set: set of peers id's
        """
        return self.gossip_keeper.pop_stop_gossip_from_peers()

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
        if time.time() - self.last_peers_request > 2:
            self.last_peers_request = time.time()
            for p in self.peers.values():
                p.send_get_peers()

    def __send_message_get_tasks(self):
        if time.time() - self.last_tasks_request > 2:
            self.last_tasks_request = time.time()
            for p in self.peers.values():
                p.send_get_tasks()

    def __connection_established(self, session, conn_id=None):
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        logger.debug("Connection to peer established. {}: {}, conn_id {}".format(session.conn.transport.getPeer().host,
                                                                                 session.conn.transport.getPeer().port,
                                                                                 conn_id))

    @staticmethod
    def __connection_failure(conn_id=None):
        logger.info("Connection to peer failure {}.".format(conn_id))

    @staticmethod
    def __connection_final_failure(conn_id=None):
        logger.info("Can't connect to peer {}.".format(conn_id))

    def __is_new_peer(self, id_):
        # id_ not in self.incoming_peers and \
        return id_ not in self.peers and \
               long(id_, 16) != self.get_key_id()

    def __remove_old_peers(self):
        cur_time = time.time()

        for peer_id in self.peers.keys():
            peer = self.peers[peer_id]
            if cur_time - peer.last_message_time > self.last_message_time_threshold:
                self.remove_peer(peer)
                peer.disconnect(PeerSession.DCRTimeout)

        if cur_time - self.last_refresh_peers > self.refresh_peers_timeout:
            self.last_refresh_peers = time.time()
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

            x = int(time.time()) % len(self.free_peers)  # get some random peer from free_peers
            peer_id = self.free_peers[x]

            if peer_id not in self.peers:
                peer = self.incoming_peers[peer_id]
                node = peer['node']

                if peer['address'] == node.pub_addr:
                    port = node.p2p_pub_port or node.p2p_prv_port
                else:
                    port = node.p2p_prv_port

                logger.info("Connecting to peer {} / {}:{}".format(peer_id, peer['address'], port))
                self.incoming_peers[peer_id]["conn_trials"] += 1  # increment connection trials
                self._add_pending_request(P2PConnTypes.Start, node, port, node.key, args={})

            self.free_peers.remove(peer_id)

    def __sync_peer_keeper(self):
        self.__remove_sessions_to_end_from_peer_keeper()
        peers_to_find = self.peer_keeper.sync()
        self.__remove_sessions_to_end_from_peer_keeper()
        if peers_to_find:
            self.send_find_nodes(peers_to_find)

    def __remove_sessions_to_end_from_peer_keeper(self):
        for peer_id in self.peer_keeper.sessions_to_end:
            self.remove_peer_by_id(peer_id)
        self.peer_keeper.sessions_to_end = []


class P2PConnTypes(object):
    """ P2P Connection Types that allows to choose right reaction  """
    Start = 1
