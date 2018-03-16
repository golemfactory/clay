import ipaddress
import logging
import random
import time
from collections import deque
from threading import Lock

from golem_messages import message

from golem.core import simplechallenge
from golem.core.variables import MAX_CONNECT_SOCKET_ADDRESSES
from golem.diag.service import DiagnosticsProvider
from golem.model import KnownHosts, MAX_STORED_HOSTS, db
from golem.network.p2p.peersession import PeerSession, PeerSessionInfo
from golem.network.transport import tcpnetwork
from golem.network.transport import tcpserver
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.ranking.manager.gossip_manager import GossipManager
from .peerkeeper import PeerKeeper, key_distance

logger = logging.getLogger(__name__)

LAST_MESSAGE_BUFFER_LEN = 5  # How many last messages should we keep
# After how many seconds from the last try should we try to connect with seed?
RECONNECT_WITH_SEED_THRESHOLD = 30
# Should nodes that connects with us solve hashcash challenge?
SOLVE_CHALLENGE = True
# Number of neighbors to notify of forwarded sessions
FORWARD_NEIGHBORS_COUNT = 3
# Forwarded sessions batch size
FORWARD_BATCH_SIZE = 12

BASE_DIFFICULTY = 5  # What should be a challenge difficulty?
HISTORY_LEN = 5  # How many entries from challenge history should we remember

TASK_INTERVAL = 10
PEERS_INTERVAL = 30
FORWARD_INTERVAL = 2

SEEDS = [
    ('94.23.57.58', 40102),
    ('94.23.57.58', 40104),
    ('94.23.196.166', 40102),
    ('94.23.196.166', 40104),
    ('188.165.227.180', 40102),
    ('188.165.227.180', 40104),
    # TODO: FOR BETA, replace with seeds.golem.network. issue GI #82
    ('seeds.test.golem.network', 40102),
    ('seeds.test.golem.network', 40104),
]


class P2PService(tcpserver.PendingConnectionsServer, DiagnosticsProvider):

    def __init__(
            self,
            node,
            config_desc,
            keys_auth,
            connect_to_known_hosts=True
    ):
        """Create new P2P Server. Listen on port for connections and
           connect to other peers. Keeps up-to-date list of peers information
           and optimal number of open connections.
        :param Node node: Information about this node
        :param ClientConfigDescriptor config_desc: configuration options
        :param KeysAuth keys_auth: authorization manager
        """
        network = tcpnetwork.TCPNetwork(
            ProtocolFactory(
                tcpnetwork.SafeProtocol,
                self,
                SessionFactory(PeerSession)
            ),
            config_desc.use_ipv6,
            limit_connection_rate=True
        )
        tcpserver.PendingConnectionsServer.__init__(self, config_desc, network)

        self.node = node
        self.keys_auth = keys_auth
        self.peer_keeper = PeerKeeper(keys_auth.key_id)
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
        self.should_solve_challenge = SOLVE_CHALLENGE
        self.challenge_history = deque(maxlen=HISTORY_LEN)
        self.last_challenge = ""
        self.base_difficulty = BASE_DIFFICULTY
        self.connect_to_known_hosts = connect_to_known_hosts
        self.key_difficulty = config_desc.key_difficulty

        # Peers options
        self.peers = {}  # active peers
        self.peer_order = []  # peer connection order
        self.incoming_peers = {}  # known peers with connections
        self.free_peers = []  # peers to which we're not connected
        self.seeds = set()
        self.used_seeds = set()

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
        self.last_forward_request = time.time()

        self.last_messages = []
        random.seed()

    def _listening_established(self, port):
        super(P2PService, self)._listening_established(port)
        self.node.p2p_prv_port = port

    def connect_to_network(self):
        self.connect_to_seeds()
        if not self.connect_to_known_hosts:
            return

        for host in KnownHosts.select() \
                .where(KnownHosts.is_seed == False):  # noqa

            ip_address = host.ip_address
            port = host.port

            logger.debug("Connecting to {}:{}".format(ip_address, port))
            try:
                socket_address = tcpnetwork.SocketAddress(ip_address, port)
                self.connect(socket_address)
            except Exception as exc:
                logger.error("Cannot connect to host {}:{}: {}"
                             .format(ip_address, port, exc))

    def connect_to_seeds(self):
        self.last_time_tried_connect_with_seed = time.time()
        if not self.connect_to_known_hosts:
            return

        for _ in range(len(self.seeds)):
            ip_address, port = self._get_next_random_seed()
            try:
                socket_address = tcpnetwork.SocketAddress(ip_address, port)
                self.connect(socket_address)
            except Exception as exc:
                logger.error("Cannot connect to seed %s:%s: %s",
                             ip_address, port, exc)
                continue
            break  # connected

    def connect(self, socket_address):
        if not self.active:
            return

        connect_info = tcpnetwork.TCPConnectInfo(
            [socket_address],
            self.__connection_established,
            P2PService.__connection_failure
        )
        self.network.connect(connect_info)

    def disconnect(self):
        peers = dict(self.peers)
        for peer in peers.values():
            peer.dropped()

    def pause(self):
        super(P2PService, self).pause()

    def resume(self):
        super(P2PService, self).resume()

    def new_connection(self, session):
        if self.active:
            session.start()
        else:
            session.disconnect(
                message.Disconnect.REASON.NoMoreMessages
            )

    def add_known_peer(self, node, ip_address, port):
        is_seed = node.is_super_node() if node else False

        try:
            with db.transaction():
                KnownHosts.delete().where(
                    (KnownHosts.ip_address == ip_address)
                    & (KnownHosts.port == port)
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
            logger.error(
                "Couldn't add known peer %r:%r : %s",
                ip_address,
                port,
                err
            )

    def set_metadata_manager(self, metadata_manager):
        self.metadata_manager = metadata_manager

    def interpret_metadata(self, *args, **kwargs):
        self.metadata_manager.interpret_metadata(*args, **kwargs)

    def sync_network(self):
        """Get information about new tasks and new peers in the network.
           Remove excess information about peers
        """
        super().sync_network(timeout=self.last_message_time_threshold)

        now = time.time()

        # We are given access to TaskServer by Client in start_network method.
        # We don't want to send GetTasks messages, before we can handle them.
        if self.task_server and now - self.last_tasks_request > TASK_INTERVAL:
            self.last_tasks_request = now
            self._send_get_tasks()

        if now - self.last_peers_request > PEERS_INTERVAL:
            self.last_peers_request = now
            self.__sync_free_peers()
            self.__sync_peer_keeper()
            self.__send_get_peers()

        if now - self.last_forward_request > FORWARD_INTERVAL:
            self.last_forward_request = now
            self._sync_forward_requests()

        self.__remove_old_peers()
        self._sync_pending()
        if len(self.peers) == 0:
            delta = time.time() - self.last_time_tried_connect_with_seed
            if delta > self.reconnect_with_seed_threshold:
                self.connect_to_seeds()

    def get_diagnostics(self, output_format):
        peer_data = []
        for peer in self.peers.values():
            peer = PeerSessionInfo(peer).get_simplified_repr()
            peer_data.append(peer)
        return self._format_diagnostics(peer_data, output_format)

    def ping_peers(self, interval):
        """ Send ping to all peers with whom this peer has open connection
        :param int interval: will send ping only if time from last ping
                             was longer than interval
        """
        for p in list(self.peers.values()):
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

    def add_peer(self, peer: PeerSession):
        """ Add a new open connection with a peer to the list of peers
        :param peer: peer session with given peer
        """
        key_id = peer.key_id
        logger.info(
            "Adding peer %r, key id difficulty: %r",
            key_id,
            self.keys_auth.get_difficulty(key_id)
        )
        with self._peer_lock:
            self.peers[key_id] = peer
            self.peer_order.append(key_id)
        # Timeouts of this session/peer will be handled in sync_network()
        try:
            self.pending_sessions.remove(peer)
        except KeyError:
            pass

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
        add_peer = force or self.__is_new_peer(key_id)
        add_peer = add_peer and self._is_address_valid(peer_info["address"],
                                                       peer_info["port"])
        if not add_peer:
            return

        logger.info(
            "add peer to incoming %r %r %r (%r)",
            peer_info["node_name"],
            peer_info["address"],
            peer_info["port"],
            key_id
        )

        self.incoming_peers[key_id] = {
            "address": peer_info["address"],
            "port": peer_info["port"],
            "node": peer_info["node"],
            "node_name": peer_info["node_name"],
            "conn_trials": 0
        }

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

        if not peer:
            logger.info("Can't remove peer {}, unknown peer".format(peer_id))

    def refresh_peer(self, peer):
        self.remove_peer(peer)
        self.try_to_add_peer({"address": peer.address,
                              "port": peer.port,
                              "node": peer.node_info,
                              "node_name": peer.node_name},
                             force=True)

    def enough_peers(self):
        """Inform whether peer has optimal or more open connections with
           other peers
        :return bool: True if peer has enough open connections with other
                      peers, False otherwise
        """
        with self._peer_lock:
            return len(self.peers) >= self.config_desc.opt_peer_num

    def set_last_message(self, type_, client_key_id, t, msg, address, port):
        """Add given message to last message buffer and inform peer keeper
           about it
        :param int type_: message time
        :param client_key_id: public key of a message sender
        :param float t: time of receiving message
        :param Message msg: received message
        :param str address: sender address
        :param int port: sender port
        """
        self.peer_keeper.set_last_message_time(client_key_id)
        if len(self.last_messages) >= self.last_message_buffer_len:
            self.last_messages = self.last_messages[
                -(self.last_message_buffer_len - 1):
            ]

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
        listening on a new one. If seed address is changed, connect to a new
        seed.
        Change configuration for resource server.
        :param ClientConfigDescriptor config_desc: new config descriptor
        """

        is_node_name_changed = self.node_name != config_desc.node_name

        tcpserver.TCPServer.change_config(self, config_desc)
        self.node_name = config_desc.node_name

        self.last_message_time_threshold = self.config_desc.p2p_session_timeout

        for peer in list(self.peers.values()):
            if (peer.port == self.config_desc.seed_port
                    and peer.address == self.config_desc.seed_host):
                return

        if self.config_desc.seed_host and self.config_desc.seed_port:
            try:
                socket_address = tcpnetwork.SocketAddress(
                    self.config_desc.seed_host,
                    self.config_desc.seed_port
                )
                self.connect(socket_address)
            except ipaddress.AddressValueError as err:
                logger.error('Invalid seed address: ' + str(err))

        if self.resource_server:
            self.resource_server.change_config(config_desc)

    def change_address(self, th_dict_repr):
        """ Change peer address in task header dictionary representation
        :param dict th_dict_repr: task header dictionary representation
                                  that should be changed
        """
        try:
            id_ = th_dict_repr["task_owner"]["key"]

            if self.peers[id_]:
                th_dict_repr["task_owner"]["pub_addr"] = self.peers[id_].address
                th_dict_repr["task_owner"]["pub_port"] = self.peers[id_].port
        except KeyError as err:
            logger.error("Wrong task representation: {}".format(err))

    def check_solution(self, solution, challenge, difficulty):
        """
        Check whether solution is valid for given challenge and it's difficulty
        :param str solution: solution to check
        :param str challenge: solved puzzle
        :param int difficulty: difficulty of a challenge
        :return boolean: true if challenge has been correctly solved,
                         false otherwise
        """
        return simplechallenge.accept_challenge(
            challenge,
            solution,
            difficulty)

    def solve_challenge(self, key_id, challenge, difficulty):
        """ Solve challenge with given difficulty for a node with key_id
        :param str key_id: key id of a node that has send this challenge
        :param str challenge: puzzle to solve
        :param int difficulty: difficulty of challenge
        :return str: solution of a challenge
        """
        self.challenge_history.append([key_id, challenge])
        solution, time_ = simplechallenge.solve_challenge(
            challenge, difficulty)
        logger.debug(
            "Solved challenge with difficulty %r in %r sec",
            difficulty,
            time_
        )
        return solution

    def get_peers_degree(self):
        """ Return peers degree level
        :return dict: dictionary where peers ids are keys and their
                      degrees are values
        """
        return {peer.key_id: peer.degree for peer in list(self.peers.values())}

    def get_key_id(self):
        """ Return node public key in a form of an id """
        return self.peer_keeper.key_num

    def set_suggested_address(self, client_key_id, addr, port):
        """Set suggested address for peer. This node will be used as first
           for connection attempt
        :param str client_key_id: peer public key
        :param str addr: peer suggested address
        :param int port: peer suggested port
                         [this argument is ignored right now]
        :return:
        """
        self.suggested_address[client_key_id] = addr

    def get_suggested_conn_reverse(self, client_key_id):
        return self.suggested_conn_reverse.get(client_key_id, False)

    def set_suggested_conn_reverse(self, client_key_id, value=True):
        self.suggested_conn_reverse[client_key_id] = value

    def get_socket_addresses(self, node_info, prv_port=None, pub_port=None):
        """ Change node info into tcp addresses. Adds a suggested address.
        :param Node node_info: node information
        :param prv_port: private port that should be used
        :param pub_port: public port that should be used
        :return:
        """
        prv_port = prv_port or node_info.p2p_prv_port
        pub_port = pub_port or node_info.p2p_pub_port

        socket_addresses = super().get_socket_addresses(
            node_info=node_info,
            prv_port=prv_port,
            pub_port=pub_port
        )

        address = self.suggested_address.get(node_info.key, None)
        if not address:
            return socket_addresses

        if self._is_address_valid(address, prv_port):
            socket_address = tcpnetwork.SocketAddress(address, prv_port)
            self._prepend_address(socket_addresses, socket_address)

        if self._is_address_valid(address, pub_port):
            socket_address = tcpnetwork.SocketAddress(address, pub_port)
            self._prepend_address(socket_addresses, socket_address)

        return socket_addresses[:MAX_CONNECT_SOCKET_ADDRESSES]

    # Kademlia functions
    #############################
    def send_find_nodes(self, peers_to_find):
        """Kademlia find node function. Send find node request
           to the closest neighbours
         of a sought node
        :param dict peers_to_find: list of nodes that should be find with
                                   their closest neighbours list
        """
        for node_key_id, neighbours in peers_to_find.items():
            for neighbour in neighbours:
                peer = self.peers.get(neighbour.key)
                if peer:
                    peer.send_find_node(node_key_id)

    # Find node
    #############################
    def find_node(self, node_key_id, alpha=None):
        """Kademlia find node function. Find closest neighbours of a node
           with given public key
        :param node_key_id: public key of a sought node
        :param alpha: number of neighbours to find
        :return list: list of information about closest neighbours
        """
        alpha = alpha or self.peer_keeper.concurrency

        if node_key_id is None:
            peers = list(self.peers.values())
            alpha = min(alpha, len(peers))
            neighbours = random.sample(peers, alpha)

            def _mapper(peer):
                return {
                    'address': peer.address,
                    'port': peer.listen_port,
                    'node_name': peer.node_name,
                    'node': peer.node_info,
                }
        else:
            neighbours = self.peer_keeper.neighbours(node_key_id, alpha)

            def _mapper(peer):
                return {
                    "address": peer.prv_addr,
                    "port": peer.prv_port,
                    "id": peer.key,
                    "node": peer,
                    "node_name": peer.node_name,
                }

        return [_mapper(peer) for peer in neighbours]

    # Resource functions
    #############################
    def set_resource_server(self, resource_server):
        """ Set resource server
        :param BaseResourceServer resource_server: resource server instance
        """
        self.resource_server = resource_server

    # TASK FUNCTIONS
    ############################
    def get_own_tasks_headers(self):
        """ Return a list of a known tasks headers
        :return list: list of task header
        """
        return self.task_server.get_own_tasks_headers()

    def get_others_tasks_headers(self):
        """ Return a list of a known tasks headers
        :return list: list of task header
        """
        return self.task_server.get_others_tasks_headers()

    def add_task_header(self, th_dict_repr):
        """ Add new task header to a list of known task headers
        :param dict th_dict_repr: new task header dictionary representation
        :return bool: True if a task header was in a right format,
                      False otherwise
        """
        return self.task_server.add_task_header(th_dict_repr)

    def remove_task_header(self, task_id) -> bool:
        """ Remove header of a task with given id from a list of a known tasks
        :param str task_id: id of a task that should be removed
        :return: False if task was already removed
        """
        return self.task_server.remove_task_header(task_id)

    def remove_task(self, task_id):
        """ Ask all peers to remove information about given task
        :param str task_id: id of a task that should be removed
        """
        for p in list(self.peers.values()):
            p.send_remove_task(task_id)

    def send_remove_task_container(self, msg_remove_task):
        for p in list(self.peers.values()):
            p.send(message.RemoveTaskContainer(remove_tasks=[msg_remove_task]))

    def want_to_start_task_session(
            self,
            key_id,
            node_info,
            conn_id,
            super_node_info=None
    ):
        """Inform peer with public key <key_id> that node from node info wants
           to start task session with him. If peer with given id is on a list
           of peers that this message will be send directly. Otherwise all
           peers will receive a request to pass this message.
        :param str key_id: key id of a node that should open a task session
        :param Node node_info: information about node that requested session
        :param str conn_id: connection id for reference
        :param Node|None super_node_info: *Default: None* information about
                                          node with public ip that took part
                                          in message transport
        """
        if not self.task_server.task_connections_helper.is_new_conn_request(
                key_id, node_info):
            self.task_server.remove_pending_conn(conn_id)
            self.task_server.remove_responses(conn_id)
            return

        if super_node_info is None and self.node.is_super_node():
            super_node_info = self.node

        connected_peer = self.peers.get(key_id)
        if connected_peer:
            if node_info.key == self.node.key:
                self.set_suggested_conn_reverse(key_id)
            connected_peer.send_want_to_start_task_session(
                node_info,
                conn_id,
                super_node_info
            )
            logger.debug("Starting task session with {}".format(key_id))
            return

        msg_snd = False

        peers = list(self.peers.values())  # may change during iteration
        distances = sorted(
            (p for p in peers if p.key_id != node_info.key and p.verified),
            key=lambda p: key_distance(key_id, p.key_id)
        )

        for peer in distances[:FORWARD_NEIGHBORS_COUNT]:
            self.task_server.task_connections_helper.forward_queue_put(
                peer, key_id, node_info, conn_id, super_node_info
            )
            msg_snd = True

        if msg_snd and node_info.key == self.node.key:
            self.task_server.add_forwarded_session_request(key_id, conn_id)

        if not msg_snd and node_info.key == self.get_key_id():
            self.task_server\
                .task_connections_helper.cannot_start_task_session(conn_id)

    def peer_want_task_session(self, node_info, super_node_info, conn_id):
        """Process request to start task session from this node to a node
           from node_info.
        :param Node node_info: node that requests task session with this node
        :param Node|None super_node_info: information about supernode
                                          that has passed this information
        :param conn_id: connection id
        """
        self.task_server.start_task_session(
            node_info,
            super_node_info,
            conn_id
        )

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
        for peer in list(self.peers.values()):
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
        for peer in list(self.peers.values()):
            peer.send_loc_rank(node_id, loc_rank)

    def safe_neighbour_loc_rank(self, neigh_id, about_id, rank):
        """
        Add local rank from neighbour to the collection
        :param str neigh_id: id of a neighbour - opinion giver
        :param str about_id: opinion is about a node with this id
        :param list rank: opinion that node <neigh_id> has about
                          node <about_id>
        :return:
        """
        self.gossip_keeper.add_neighbour_loc_rank(neigh_id, about_id, rank)

    def pop_neighbours_loc_ranks(self):
        """Return all local ranks that was collected in that round
           and clear the rank list
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

    # In the future it may be changed to something more flexible
    # and more connected with key_id
    def _get_difficulty(self, key_id):
        return self.base_difficulty

    def _get_challenge(self, key_id):
        self.last_challenge = simplechallenge.create_challenge(
            self.challenge_history,
            self.last_challenge
        )
        return self.last_challenge

    #############################
    # PRIVATE SECTION
    #############################

    def __send_get_peers(self):
        for p in list(self.peers.values()):
            p.send_get_peers()

    def _send_get_tasks(self):
        for p in list(self.peers.values()):
            p.send_get_tasks()

    def __connection_established(self, session, conn_id: str):
        peer_conn = session.conn.transport.getPeer()
        ip_address = peer_conn.host
        port = peer_conn.port

        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)

        logger.debug("Connection to peer established. %s: %s, conn_id %s",
                     ip_address, port, conn_id)

    @staticmethod
    def __connection_failure(conn_id: str):
        logger.debug("Connection to peer failure %s.", conn_id)

    @staticmethod
    def __connection_final_failure(conn_id: str):
        logger.debug("Can't connect to peer %s.", conn_id)

    def __is_new_peer(self, id_):
        return id_ not in self.incoming_peers\
            and not self.__is_connected_peer(id_)

    def __is_connected_peer(self, id_):
        return id_ in self.peers or int(id_, 16) == self.get_key_id()

    def __remove_old_peers(self):
        for peer in list(self.peers.values()):
            delta = time.time() - peer.last_message_time
            if delta > self.last_message_time_threshold:
                self.remove_peer(peer)
                peer.disconnect(
                    message.Disconnect.REASON.Timeout
                )

    def _sync_forward_requests(self):
        helper = self.task_server.task_connections_helper
        entries = helper.forward_queue_get(FORWARD_BATCH_SIZE)

        for entry in entries:
            peer, args = entry[0](), entry[1]  # weakref
            if peer:
                peer.send_set_task_session(*args)

    def __sync_free_peers(self):
        while self.free_peers and not self.enough_peers():

            peer_id = random.choice(self.free_peers)
            self.free_peers.remove(peer_id)

            if not self.__is_connected_peer(peer_id):
                peer = self.incoming_peers[peer_id]
                node = peer['node']

                # increment connection trials
                self.incoming_peers[peer_id]["conn_trials"] += 1
                self._add_pending_request(
                    P2PConnTypes.Start,
                    node,
                    prv_port=node.p2p_prv_port,
                    pub_port=node.p2p_pub_port,
                    args={}
                )

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

        for config_seed in self.config_desc.seeds.split(None):
            try:
                ip_address, port = config_seed.split(':', 1)
                port = int(port)
                # Verify that ip_address is valid.
                # Throws ipaddress.AddressValueError.
                ipaddress.ip_address(ip_address)
            except ValueError:
                logger.info(
                    "Invalid seed from config: %r. Ignoring.",
                    config_seed
                )
                continue
            self.seeds.add((ip_address, port))

    def _get_next_random_seed(self):
        # this loop won't execute more than twice
        while True:
            for seed in random.sample(self.seeds, k=len(self.seeds)):
                if seed not in self.used_seeds:
                    self.used_seeds.add(seed)
                    return seed
            self.used_seeds = set()

    def __remove_sessions_to_end_from_peer_keeper(self):
        for node in self.peer_keeper.sessions_to_end:
            self.remove_peer_by_id(node.key)
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
