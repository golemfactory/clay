import logging
import time

from golem.core.crypto import ECIESDecryptionError
from golem.network.transport import message
from golem.network.transport.message import MessagePing, MessagePong, MessageGetPeers,\
    MessagePeers, MessageGetTasks, MessageTasks, MessageRemoveTask, MessageGetResourcePeers, MessageResourcePeers, \
    MessageDegree, MessageGossip, MessageStopGossip, MessageLocRank, MessageFindNode, MessageRandVal, \
    MessageWantToStartTaskSession, MessageSetTaskSession, MessageNatHole, MessageNatTraverseFailure, \
    MessageInformAboutNatTraverseFailure, MessageChallengeSolution
from golem.network.transport.session import BasicSafeSession
from golem.network.transport.tcpnetwork import SafeProtocol

logger = logging.getLogger(__name__)

P2P_PROTOCOL_ID = 12


class PeerSessionInfo(object):
    attributes = [
        'address', 'port',
        'verified', 'degree', 'key_id',
        'node_name', 'node_info',
        'listen_port', 'conn_id'
    ]

    def __init__(self, session):
        for attr in self.attributes:
            setattr(self, attr, getattr(session, attr))

    def get_simplified_repr(self):
        repr = self.__dict__
        del repr['node_info']
        return repr


class PeerSession(BasicSafeSession):
    """ Session for Golem P2P Network. """

    ConnectionStateType = SafeProtocol

    # Disconnect reason
    DCRDuplicatePeers = "Duplicate peers"
    DCRTooManyPeers = "Too many peers"
    DCRRefresh = "Refresh"

    def __init__(self, conn):
        """
        Create new session
        :param Protocol conn: connection protocol implementation that this session should enhance
        :return None:
        """
        BasicSafeSession.__init__(self, conn)
        self.p2p_service = self.conn.server

        # Information about peer
        self.degree = 0
        self.node_name = ""
        self.node_info = None
        self.listen_port = None

        self.conn_id = None

        self.solve_challenge = False  # Verification by challenge not a random value
        self.challenge = None
        self.difficulty = 0

        self.can_be_unverified.extend([message.MessageHello.TYPE, MessageRandVal.TYPE, MessageChallengeSolution.TYPE])
        self.can_be_unsigned.extend([message.MessageHello.TYPE])
        self.can_be_not_encrypted.extend([message.MessageHello.TYPE])

        self.__set_msg_interpretations()

    def __str__(self):
        return "{} : {}".format(self.address, self.port)

    def dropped(self):
        """
        Close connection and inform p2p service about disconnection
        """
        BasicSafeSession.dropped(self)
        self.p2p_service.remove_peer(self)

    def interpret(self, msg):
        """
        React to specific message. Disconnect, if message type is unknown for that session.
        Inform p2p service about last message.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        self.p2p_service.set_last_message("<-", self.key_id, time.localtime(), msg, self.address, self.port)
        BasicSafeSession.interpret(self, msg)

    def send(self, msg, send_unverified=False):
        """ Send given message if connection was verified or send_unverified option is set to True.
        :param Message message: message to be sent.
        :param boolean send_unverified: should message be sent even if the connection hasn't been verified yet?
        """
        BasicSafeSession.send(self, msg, send_unverified)
        self.p2p_service.set_last_message("->", self.key_id, time.localtime(), msg, self.address, self.port)

    def sign(self, msg):
        """ Sign given message
        :param Message msg: message to be signed
        :return Message: signed message
        """
        if self.p2p_service is None:
            logger.error("P2PService is None, can't sign a message.")
            return None

        msg.sig = self.p2p_service.sign(msg.get_short_hash())
        return msg

    def verify(self, msg):
        """ Verify signature on given message. Check if message was signed with key_id from this connection.
        :param Message msg: message to be verified
        :return boolean: True if message was signed with key_id from this connection
        """
        return self.p2p_service.verify_sig(msg.sig, msg.get_short_hash(), self.key_id)

    def encrypt(self, data):
        """ Encrypt given data using key_id from this connection.
        :param str data: serialized message to be encrypted
        :return str: encrypted message
        """
        return self.p2p_service.encrypt(data, self.key_id)

    def decrypt(self, data):
        """
        Decrypt given data using private key. If during decryption AssertionError occurred this may mean that
        data is not encrypted simple serialized message. In that case unaltered data are returned.
        :param str data: data to be decrypted
        :return str msg: decrypted message
        """
        if not self.p2p_service:
            return data

        try:
            msg = self.p2p_service.decrypt(data)
        except ECIESDecryptionError as err:
            logger.info("Failed to decrypt message from {}:{}, "
                        "maybe it's not encrypted? {}".format(self.address, self.port, err))
            msg = data

        return msg

    def start(self):
        """
        Send first hello message
        """
        logger.info("Starting peer session {} : {}".format(self.address, self.port))
        self.__send_hello()

    def hello(self):
        self.__send_hello()

    def ping(self, interval):
        """ Will send ping message if time from last message was longer than interval
        :param float interval: number of seconds that should pass until ping message may be send
        """
        if time.time() - self.last_message_time > interval:
            self.__send_ping()

    def send_get_peers(self):
        """  Send get peers message """
        self.send(MessageGetPeers())

    def send_get_tasks(self):
        """  Send get tasks message """
        self.send(MessageGetTasks())

    def send_remove_task(self, task_id):
        """  Send remove task  message
         :param str task_id: task to be removed
        """
        self.send(MessageRemoveTask(task_id))

    def send_get_resource_peers(self):
        """ Send get resource peers message """
        self.send(MessageGetResourcePeers())

    def send_degree(self, degree):
        """ Send degree message
         :param int degree: degree of this node
        """
        self.send(MessageDegree(degree))

    def send_gossip(self, gossip):
        """ Send message with gossip
         :param list gossip: gossip to be send
        """
        self.send(MessageGossip(gossip))

    def send_stop_gossip(self):
        """ Send stop gossip message """
        self.send(MessageStopGossip())

    def send_loc_rank(self, node_id, loc_rank):
        """ Send local opinion about given node
        :param node_id: send opinion about node with this id
        :param LocalRank loc_rank: opinion bout node
        :return:
        """
        self.send(MessageLocRank(node_id, loc_rank))

    def send_find_node(self, key_num):
        """ Send find node message
        :param long key_num: key of a node to be find """
        self.send(MessageFindNode(key_num))

    def send_want_to_start_task_session(self, node_info, conn_id, super_node_info):
        """ Send request for starting task session with given node
        :param Node node_info: information about this node.
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        """
        self.send(MessageWantToStartTaskSession(node_info, conn_id, super_node_info))

    def send_set_task_session(self, key_id, node_info, conn_id, super_node_info):
        """ Send information that node from node_info want to start task session with key_id node
        :param key_id: target node key
        :param Node node_info: information about requestor
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        """
        self.send(MessageSetTaskSession(key_id, node_info, conn_id, super_node_info))

    def send_task_nat_hole(self, key_id, address, port, conn_id):
        """
        Send information about nat hole
        :param key_id: key of the node behind nat hole
        :param str address: address of the nat hole
        :param int port: port of the nat hole
        :param uuid conn_id: connection id for reference
        """
        self.send(MessageNatHole(key_id, address, port, conn_id))

    def send_inform_about_nat_traverse_failure(self, key_id, conn_id):
        """
        Send request to inform node with key_id about unsuccessful nat traverse.
        :param key_id: key of the node that should be inform about failure
        :param uuid conn_id: connection id for reference
        """
        self.send(MessageInformAboutNatTraverseFailure(key_id, conn_id))

    def send_nat_traverse_failure(self, conn_id):
        """
        Send information about unsuccessful nat traverse
        :param uuid conn_id: connection id for reference
        :return:
        """
        self.send(MessageNatTraverseFailure(conn_id))

    def _react_to_ping(self, msg):
        self._send_pong()

    def _react_to_pong(self, msg):
        self.p2p_service.pong_received(self.key_id)

    def _react_to_hello(self, msg):
        self.node_name = msg.node_name
        self.node_info = msg.node_info
        self.listen_port = msg.port

        next_hello = self.key_id == msg.client_key_id
        self.key_id = msg.client_key_id

        metadata = msg.metadata
        solve_challenge = msg.solve_challenge
        challenge = msg.challenge
        difficulty = msg.difficulty

        if not self.verify(msg):
            logger.warning("Wrong signature for Hello msg from {}:{}".format(self.address, self.port))
            self.disconnect(PeerSession.DCRUnverified)
            return

        if msg.proto_id != P2P_PROTOCOL_ID:
            logger.info("P2P protocol version mismatch %r vs %r (local) for node %r:%r", msg.proto_id, P2P_PROTOCOL_ID, self.address, self.port)
            self.disconnect(PeerSession.DCRProtocolVersion)
            return

        self.p2p_service.add_to_peer_keeper(self.node_info)
        self.p2p_service.interpret_metadata(metadata,
                                            self.address,
                                            self.listen_port,
                                            self.node_info)

        if self.p2p_service.enough_peers():
            logger_msg = "TOO MANY PEERS, DROPPING CONNECTION: {} {}: {}" \
                .format(self.node_name, self.address, self.port)
            logger.info(logger_msg)
            nodes_info = self.p2p_service.find_node(self.p2p_service.get_key_id())
            self.send(MessagePeers(nodes_info))
            self.disconnect(PeerSession.DCRTooManyPeers)

            self.p2p_service.try_to_add_peer({"address": self.address,
                                              "port": msg.port,
                                              "node": self.node_info,
                                              "node_name": self.node_name,
                                              "conn_trials": 0})
            return

        p = self.p2p_service.find_peer(self.key_id)

        if p:
            if not next_hello and p != self and p.conn.opened:
                # self.sendPing()
                logger_msg = "PEER DUPLICATED: {} {} : {}".format(p.node_name, p.address, p.port)
                logger.warning("{} AND {} : {}".format(logger_msg, msg.node_name, msg.port))
                self.disconnect(PeerSession.DCRDuplicatePeers)
                return

            if solve_challenge and not self.verified:
                self._solve_challenge(challenge, difficulty)
        else:
            self.p2p_service.add_peer(self.key_id, self)
            if solve_challenge:
                self._solve_challenge(challenge, difficulty)
            else:
                self.send(MessageRandVal(msg.rand_val), send_unverified=True)
            self.__send_hello()

        # print "Add peer to client uid:{} address:{} port:{}".format(self.node_name, self.address, self.port)

    def _solve_challenge(self, challenge, difficulty):
        solution = self.p2p_service.solve_challenge(self.key_id, challenge, difficulty)
        self.send(MessageChallengeSolution(solution), send_unverified=True)

    def _react_to_get_peers(self, msg):
        self.__send_peers()

    def _react_to_peers(self, msg):
        peers_info = msg.peers_array
        self.degree = len(peers_info)
        for pi in peers_info:
            self.p2p_service.try_to_add_peer(pi)

    def _react_to_get_tasks(self, msg):
        tasks = self.p2p_service.get_tasks_headers()
        self.__send_tasks(tasks)

    def _react_to_tasks(self, msg):
        for t in msg.tasks_array:
            if not self.p2p_service.add_task_header(t):
                self.disconnect(PeerSession.DCRBadProtocol)

    def _react_to_remove_task(self, msg):
        self.p2p_service.remove_task_header(msg.task_id)

    def _react_to_get_resource_peers(self, msg):
        self.__send_resource_peers()

    def _react_to_resource_peers(self, msg):
        self.p2p_service.set_resource_peers(msg.resource_peers)

    def _react_to_degree(self, msg):
        self.degree = msg.degree

    def _react_to_gossip(self, msg):
        self.p2p_service.hear_gossip(msg.gossip)

    def _react_to_stop_gossip(self, msg):
        self.p2p_service.register_that_peer_stopped_gossiping(self.key_id)

    def _react_to_loc_rank(self, msg):
        self.p2p_service.safe_neighbour_loc_rank(self.key_id, msg.node_id, msg.loc_rank)

    def _react_to_find_node(self, msg):
        nodes_info = self.p2p_service.find_node(msg.node_key_id)
        self.send(MessagePeers(nodes_info))

    def _react_to_rand_val(self, msg):
        # if self.solve_challenge:
        #    return
        if self.rand_val == msg.rand_val:
            self.__set_verified_conn()
        else:
            self.disconnect(PeerSession.DCRUnverified)

    def _react_to_challenge_solution(self, msg):
        if not self.solve_challenge:
            self.disconnect(PeerSession.DCRBadProtocol)
            return
        good_solution = self.p2p_service.check_solution(msg.solution, self.challenge, self.difficulty)
        if good_solution:
            self.__set_verified_conn()
            self.solve_challenge = False
        else:
            self.disconnect(PeerSession.DCRUnverified)

    def _react_to_want_to_start_task_session(self, msg):
        self.p2p_service.peer_want_task_session(msg.node_info, msg.super_node_info, msg.conn_id)

    def _react_to_set_task_session(self, msg):
        self.p2p_service.want_to_start_task_session(msg.key_id, msg.node_info, msg.conn_id, msg.super_node_info)

    def _react_to_nat_hole(self, msg):
        self.p2p_service.traverse_nat(msg.key_id, msg.addr, msg.port, msg.conn_id, self.key_id)

    def _react_to_nat_traverse_failure(self, msg):
        self.p2p_service.traverse_nat_failure(msg.conn_id)

    def _react_to_inform_about_nat_traverse_failure(self, msg):
        self.p2p_service.send_nat_traverse_failure(msg.key_id, msg.conn_id)

    def _react_to_disconnect(self, msg):
        super(PeerSession, self)._react_to_disconnect(msg)

    def _send_pong(self):
        self.send(MessagePong())

    def __send_hello(self):
        self.solve_challenge = self.key_id and self.p2p_service.should_solve_challenge or False
        challenge_kwargs = {}
        if self.solve_challenge:
            self.challenge = challenge_kwargs['challenge'] = self.p2p_service._get_challenge(self.key_id)
            self.difficulty = challenge_kwargs['difficulty'] = self.p2p_service._get_difficulty(self.key_id)
        msg = message.MessageHello(
            proto_id=P2P_PROTOCOL_ID,
            port=self.p2p_service.cur_port,
            node_name=self.p2p_service.node_name,
            client_key_id=self.p2p_service.keys_auth.get_key_id(),
            node_info=self.p2p_service.node,
            rand_val=self.rand_val,
            metadata=self.p2p_service.metadata_manager.get_metadata(),
            solve_challenge=self.solve_challenge,
            **challenge_kwargs
        )
        self.send(msg, send_unverified=True)

    def __send_ping(self):
        self.send(MessagePing())

    def __send_peers(self):
        peers_info = []
        for p in self.p2p_service.peers.values():
            peers_info.append({
                "address": p.address,
                "port": p.listen_port,
                "node_name": p.node_name,
                "node": p.node_info
            })
        self.send(MessagePeers(peers_info))

    def __send_tasks(self, tasks):
        self.send(MessageTasks(tasks))

    def __send_resource_peers(self):
        resource_peers = self.p2p_service.get_resource_peers()
        self.send(MessageResourcePeers(resource_peers))

    def __set_verified_conn(self):
        self.verified = True
        self.p2p_service.verified_conn(self.conn_id)
        self.p2p_service.add_known_peer(self.node_info, self.address, self.port)
        self.p2p_service.set_suggested_address(self.key_id, self.address, self.port)

    def __set_msg_interpretations(self):
        self.__set_basic_msg_interpretations()
        self.__set_resource_msg_interpretations()
        self.__set_ranking_msg_interpretations()

    def __set_basic_msg_interpretations(self):
        self._interpretation.update({
            MessagePing.TYPE: self._react_to_ping,
            MessagePong.TYPE: self._react_to_pong,
            message.MessageHello.TYPE: self._react_to_hello,
            MessageChallengeSolution.TYPE: self._react_to_challenge_solution,
            MessageGetPeers.TYPE: self._react_to_get_peers,
            MessagePeers.TYPE: self._react_to_peers,
            MessageGetTasks.TYPE: self._react_to_get_tasks,
            MessageTasks.TYPE: self._react_to_tasks,
            MessageRemoveTask.TYPE: self._react_to_remove_task,
            MessageFindNode.TYPE: self._react_to_find_node,
            MessageRandVal.TYPE: self._react_to_rand_val,
            MessageWantToStartTaskSession.TYPE: self._react_to_want_to_start_task_session,
            MessageSetTaskSession.TYPE: self._react_to_set_task_session,
            MessageNatHole.TYPE: self._react_to_nat_hole,
            MessageNatTraverseFailure.TYPE: self._react_to_nat_traverse_failure,
            MessageInformAboutNatTraverseFailure.TYPE: self._react_to_inform_about_nat_traverse_failure
        })

    def __set_resource_msg_interpretations(self):
        self._interpretation.update({
            MessageGetResourcePeers.TYPE: self._react_to_get_resource_peers,
            MessageResourcePeers.TYPE: self._react_to_resource_peers,
        })

    def __set_ranking_msg_interpretations(self):
        self._interpretation.update({
            MessageDegree.TYPE: self._react_to_degree,
            MessageGossip.TYPE: self._react_to_gossip,
            MessageLocRank.TYPE: self._react_to_loc_rank,
            MessageStopGossip.TYPE: self._react_to_stop_gossip,
        })
