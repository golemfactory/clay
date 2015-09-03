import time
import logging
import random

from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcp_network import TCPNetwork, TCPConnectInfo, TCPAddress, SafeProtocol
from golem.network.transport.tcp_server import TCPServer
from golem.network.transport.server import Server
from golem.network.p2p.peer_session import PeerSession

from PeerKeeper import PeerKeeper

logger = logging.getLogger(__name__)


class P2PService(TCPServer):
    def __init__(self, node, config_desc, keys_auth, use_ipv6=False):
        network = TCPNetwork(ProtocolFactory(SafeProtocol, self, SessionFactory(PeerSession)), use_ipv6)
        TCPServer.__init__(self, config_desc, network)

        self.peers = {}
        self.all_peers = []
        self.client_uid = self.config_desc.clientUid
        self.last_peers_request = time.time()
        self.last_get_tasks_request = time.time()
        self.incoming_peers = {}
        self.free_peers = []
        self.task_server = None
        self.node = node
        self.last_message_time_threshold = self.config_desc.p2pSessionTimeout
        self.refresh_peers_timeout = 1200  # FIXME
        self.last_refresh_peers = time.time()

        self.last_messages = []

        self.resourcePort = 0
        self.resource_peers = {}
        self.resource_server = None
        self.gossip = []
        self.stop_gossip_from_peers = set()
        self.neighbour_loc_rank_buff = []

        self.keys_auth = keys_auth
        self.peer_keeper = PeerKeeper(keys_auth.get_key_id())
        self.suggested_address = {}

        self.connections_to_set = {}

        self.manager_session = None

        self.connect_to_network()

    def connect_to_network(self):
        """ Start listening on the port from configuration and try to connect to the seed node """
        self.start_accepting()
        tcp_address = TCPAddress(self.config_desc.seedHost, self.config_desc.seedHostPort)
        if tcp_address.is_proper():
            self.__connect(tcp_address)

    def set_task_server(self, task_server):
        self.task_server = task_server

    def sync_network(self):

        self.__send_get_peers()

        if self.task_server:
            self.__send_message_get_tasks()

        self.__remove_old_peers()
        self.__sync_peer_keeper()

    def __sync_peer_keeper(self):
        self.__remove_sessions_to_end_from_peer_keeper()
        nodes_to_find = self.peer_keeper.sync_network()
        self.__remove_sessions_to_end_from_peer_keeper()
        if nodes_to_find:
            self.send_find_nodes(nodes_to_find)

    def __remove_sessions_to_end_from_peer_keeper(self):
        for peer_id in self.peer_keeper.sessionsToEnd:
            self.remove_peer_by_id(peer_id)
        self.peer_keeper.sessionsToEnd = []

    def new_connection(self, session):
        self.all_peers.append(session)
        session.start()

    def ping_peers(self, interval):
        for p in self.peers.values():
            p.ping(interval)

    def find_peer(self, peer_id):
        return self.peers.get(peer_id)

    def get_peers(self):
        return self.peers

    def add_peer(self, id_, peer):

        self.peers[id_] = peer
        self.__send_degree()

    def add_to_peer_keeper(self, id_, peer_key_id, address, port, node_info):
        peer_to_ping_info = self.peer_keeper.add_peer(peer_key_id, id_, address, port, node_info)
        if peer_to_ping_info and peer_to_ping_info.nodeId in self.peers:
            peer_to_ping = self.peers[peer_to_ping_info.nodeId]
            if peer_to_ping:
                peer_to_ping.ping(0)

    def pong_received(self, id_, peer_key_id, address, port):
        self.peer_keeper.pong_received(peer_key_id, id_, address, port)

    def try_to_add_peer(self, peer_info):
        if self.__is_new_peer(peer_info["id"]):
            logger.info("add peer to incoming {} {} {}".format(peer_info["id"],
                                                               peer_info["address"],
                                                               peer_info["port"]))
            self.incoming_peers[peer_info["id"]] = {"address": peer_info["address"],
                                                    "port": peer_info["port"],
                                                    "node": peer_info["node"],
                                                    "conn_trials": 0}
            self.free_peers.append(peer_info["id"])
            logger.debug(self.incoming_peers)

    def remove_peer(self, peer_session):

        if peer_session in self.all_peers:
            self.all_peers.remove(peer_session)

        for p in self.peers.keys():
            if self.peers[p] == peer_session:
                del self.peers[p]

        self.__send_degree()

    def remove_peer_by_id(self, peer_id):
        peer = self.peers.get(peer_id)
        if not peer:
            logger.info("Can't remove peer {}, unknown peer".format(peer_id))
            return
        if peer in self.all_peers:
            self.all_peers.remove(peer)
        del self.peers[peer_id]

        self.__send_degree()

    def enough_peers(self):
        return len(self.peers) >= self.config_desc.optNumPeers

    def set_last_message(self, type_, client_key_id, t, msg, address, port):
        self.peer_keeper.setLastMessageTime(client_key_id)
        if len(self.last_messages) >= 5:
            self.last_messages = self.last_messages[-4:]

        self.last_messages.append([type_, t, address, port, msg])

    def get_last_messages(self):
        return self.last_messages

    def manager_session_disconnect(self, uid):
        self.manager_session = None

    def change_config(self, config_desc):
        """ Change configuration descriptor. If listening port is changed, than stop listening on old port and start
        listening on a new one. If seed address is changed, connect to a new seed.
        Change configuration for resource server.
        :param ClientConfigDescriptor config_desc: new config descriptor
        """

        TCPServer.change_config(self, config_desc)

        self.last_message_time_threshold = self.config_desc.p2pSessionTimeout

        for peer in self.peers.values():
            if (peer.port == self.config_desc.seedHostPort) and (peer.address == self.config_desc.seedHostPort):
                return

        tcp_address = TCPAddress(self.config_desc.seedHost, self.config_desc.seedHostPort)
        if tcp_address.is_proper():
            self.__connect(tcp_address)

        if self.resource_server:
            self.resource_server.change_config(config_desc)

    def change_address(self, th_dict_repr):
        try:
            id_ = th_dict_repr["client_id"]

            if self.peers[id_]:
                th_dict_repr["address"] = self.peers[id_].address
                th_dict_repr["port"] = self.peers[id_].port
        except Exception, err:
            logger.error("Wrong task representation: {}".format(str(err)))

    def get_listen_params(self):
        return self.cur_port, self.client_uid, self.keys_auth.get_key_id(), self.node

    def get_peers_degree(self):
        return {peer.id: peer.degree for peer in self.peers.values()}

    def get_key_id(self):
        return self.peer_keeper.pper_key_id

    def encrypt(self, message, public_key):
        if public_key == 0:
            return message
        return self.keys_auth.encrypt(message, public_key)

    def decrypt(self, message):
        return self.keys_auth.decrypt(message)

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

    def set_suggested_address(self, client_key_id, addr, port):
        self.suggested_address[client_key_id] = addr

    # Kademlia functions
    #############################
    def send_find_nodes(self, nodes_to_find):
        for node_key_id, neighbours in nodes_to_find.iteritems():
            for neighbour in neighbours:
                peer = self.peers.get(neighbour.nodeId)
                if peer:
                    peer.send_find_node(node_key_id)

    # Find node
    #############################
    def find_node(self, node_key_id):
        neighbours = self.peer_keeper.neighbours(node_key_id)
        nodes_info = []
        for n in neighbours:
            nodes_info.append({"address": n.ip, "port": n.port, "id": n.nodeId, "node": n.node_info})
        return nodes_info

    # Resource functions
    #############################
    def set_resource_server(self, resource_server):
        self.resource_server = resource_server

    def set_resource_peer(self, addr, port):
        self.resourcePort = port
        self.resource_peers[self.client_uid] = [addr, port, self.keys_auth.get_key_id(), self.node]

    def send_get_resource_peers(self):
        for p in self.peers.values():
            p.send_get_resource_peers()

    def get_resource_peers(self):
        resource_peers_info = []
        for client_id, [addr, port, key_id, node_info] in self.resource_peers.iteritems():
            resource_peers_info.append({'client_id': client_id, 'addr': addr, 'port': port, 'key_id': key_id,
                                        'node': node_info})

        return resource_peers_info

    def set_resource_peers(self, resource_peers):
        for peer in resource_peers:
            try:
                if peer['client_id'] != self.client_uid:
                    self.resource_peers[peer['client_id']] = [peer['addr'], peer['port'], peer['key_id'], peer['node']]
            except Exception, err:
                logger.error("Wrong set peer message (peer: {}): {}".format(peer, str(err)))
        resource_peers_copy = self.resource_peers.copy()
        if self.client_uid in resource_peers_copy:
            del resource_peers_copy[self.client_uid]
        self.resource_server.set_resource_peers(resource_peers_copy)

    def put_resource(self, resource, addr, port, copies):
        self.resource_server.put_resource(resource, addr, port, copies)

    # TASK FUNCTIONS
    ############################
    def get_tasks_headers(self):
        return self.task_server.get_tasks_headers()

    def add_task_header(self, th_dict_repr):
        return self.task_server.add_task_header(th_dict_repr)

    def remove_task_header(self, task_id):
        return self.task_server.remove_task_header(task_id)

    def remove_task(self, task_id):
        for p in self.peers.values():
            p.send_remove_task(task_id)

    def want_to_start_task_session(self, key_id, node_info, conn_id, super_node_info=None):
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
            self.task_server.final_conn_failure(conn_id)

    def inform_about_task_nat_hole(self, key_id, rv_key_id, addr, port, ans_conn_id):
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
        # TODO Reakcja powinna nastapic tylko na pierwszy taki komunikat
        self.task_server.startTaskSession(node_info, super_node_info, conn_id)

    def peer_want_to_set_task_session(self, key_id, node_info, conn_id, super_node_info):
        logger.debug("Peer want to set task session with {}".format(key_id))
        if conn_id in self.connections_to_set:
            return

        # TODO Lepszy mechanizm wyznaczania supernode'a
        if super_node_info is None and self.node.isSuperNode():
            super_node_info = self.node

        # TODO Te informacje powinny wygasac (byc usuwane po jakims czasie)
        self.connections_to_set[conn_id] = (key_id, node_info, time.time())
        self.want_to_start_task_session(key_id, node_info, conn_id, super_node_info)

    #############################
    # RANKING FUNCTIONS          #
    #############################
    def send_gossip(self, gossip, send_to):
        for peer_id in send_to:
            peer = self.find_peer(peer_id)
            if peer is not None:
                peer.send_gossip(gossip)

    def hear_gossip(self, gossip):
        self.gossip.append(gossip)

    def pop_gossip(self):
        gossip = self.gossip
        self.gossip = []
        return gossip

    def send_stop_gossip(self):
        for peer in self.peers.values():
            peer.send_stop_gossip()

    def stop_gossip(self, id_):
        self.stop_gossip_from_peers.add(id_)

    def pop_stop_gossip_form_peers(self):
        stop = self.stop_gossip_from_peers
        self.stop_gossip_from_peers = set()
        return stop

    def push_local_rank(self, node_id, loc_rank):
        for peer in self.peers.values():
            peer.send_loc_rank(node_id, loc_rank)

    def safe_neighbour_loc_rank(self, neigh_id, about_id, rank):
        self.neighbour_loc_rank_buff.append([neigh_id, about_id, rank])

    def pop_neighbours_loc_ranks(self):
        nrb = self.neighbour_loc_rank_buff
        self.neighbour_loc_rank_buff = []
        return nrb

    #############################
    # PRIVATE SECTION
    #############################
    def __connect(self, tcp_address):
        connect_info = TCPConnectInfo([tcp_address], self.__connection_established,
                                      P2PService.__connection_failure)
        self.network.connect(connect_info)

    def __connect_to_host(self, peer):
        addr = self.suggested_address.get(peer['node'].key)
        tcp_addresses = P2PService.__node_info_to_tcp_addresses(peer['node'], peer['port'])
        if addr:
            tcp_addresses = [TCPAddress(addr, peer['port'])] + tcp_addresses
        connect_info = TCPConnectInfo(tcp_addresses, self.__connection_established, self.__connection_failure)
        self.network.connect(connect_info)

    # Tmp function: to be remove
    @staticmethod
    def __node_info_to_tcp_addresses(node_info, port):
        tcp_addresses = [TCPAddress(i, port) for i in node_info.prvAddresses]
        if node_info.pubPort:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, node_info.pubPort))
        else:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, port))
        return tcp_addresses

    def __send_get_peers(self):
        while len(self.peers) < self.config_desc.optNumPeers:
            if len(self.free_peers) == 0:
                peer = None  # FIXME
                #                peer = self.peer_keeper.getRandomKnownNode()
                if not peer or peer.nodeId in self.peers:
                    if time.time() - self.last_peers_request > 2:
                        self.last_peers_request = time.time()
                        for p in self.peers.values():
                            p.send_get_peers()
                else:
                    self.try_to_add_peer({"id": peer.nodeId, "address": peer.ip, "port": peer.port,
                                          "node": peer.node_info})
                break

            x = int(time.time()) % len(self.free_peers)  # get some random peer from free_peers
            peer = self.free_peers[x]
            self.incoming_peers[self.free_peers[x]]["conn_trials"] += 1  # increment connection trials
            logger.info("Connecting to peer {}".format(peer))
            # self.__connect(self.incoming_peers[peer]["address"], self.incoming_peers[peer]["port"])
            self.__connect_to_host(self.incoming_peers[peer])
            self.free_peers.remove(peer)

    def __send_message_get_tasks(self):
        if time.time() - self.last_get_tasks_request > 2:
            self.last_get_tasks_request = time.time()
            for p in self.peers.values():
                p.send_get_tasks()

    def __connection_established(self, session):
        self.all_peers.append(session)

        logger.debug("Connection to peer established. {}: {}".format(session.conn.transport.getPeer().host,
                                                                     session.conn.transport.getPeer().port))

    @staticmethod
    def __connection_failure():
        logger.error("Connection to peer failure.")

    def __is_new_peer(self, id_):
        if id_ in self.incoming_peers or id_ in self.peers or id_ == self.client_uid:
            return False
        else:
            return True

    def __remove_old_peers(self):
        cur_time = time.time()
        for peer_id in self.peers.keys():
            if cur_time - self.peers[peer_id].last_message_time > self.last_message_time_threshold:
                self.peers[peer_id].disconnect(PeerSession.DCRTimeout)

        if cur_time - self.last_refresh_peers > self.refresh_peers_timeout:
            self.last_refresh_peers = time.time()
            if len(self.peers) > 1:
                peer_id = random.choice(self.peers.keys())
                self.peers[peer_id].disconnect(PeerSession.DCRRefresh)

    def __send_degree(self):
        degree = len(self.peers)
        for p in self.peers.values():
            p.send_degree(degree)
