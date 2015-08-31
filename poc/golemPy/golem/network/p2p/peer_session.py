import time
import logging

from golem.network.transport.message import MessageHello, MessagePing, MessagePong, MessageDisconnect, MessageGetPeers, MessagePeers, \
    MessageGetTasks, MessageTasks, MessageRemoveTask, MessageGetResourcePeers, MessageResourcePeers, MessageDegree, \
    MessageGossip, MessageStopGossip, MessageLocRank, MessageFindNode, MessageRandVal, MessageWantToStartTaskSession, \
    MessageSetTaskSession, MessageNatHole, MessageNatTraverseFailure, MessageInformAboutNatTraverseFailure
from golem.network.transport.tcp_network import SafeProtocol
from golem.network.transport.session import BasicSafeSession

logger = logging.getLogger(__name__)


class PeerSession(BasicSafeSession):
    """ Session for Golem P2P Network. """

    ConnectionStateType = SafeProtocol

    # Disconnect reason
    DCRDuplicatePeers = "Duplicate peers"
    DCRTooManyPeer = "Too many peers"
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
        self.node_id = None
        self.node_info = None
        self.listen_port = None

        self.can_be_unverified.extend([MessageHello.Type, MessageRandVal.Type])
        self.can_be_unsigned.extend([MessageHello.Type])
        self.can_be_not_encrypted.extend([MessageHello.Type])

        self.__set_msg_interpretations()

    def __str__(self):
        return "{} : {}".format(self.address, self.port)

    def dropped(self):
        """
        Close connection and inform p2p service about disconnection
        """
        BasicSafeSession.dropped(self)
        self.p2p_service.removePeer(self)

    def interpret(self, msg):
        """
        React to specific message. Disconnect, if message type is unknown for that session.
        Inform p2p service about last message.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        self.p2p_service.setLastMessage("<-", self.key_id, time.localtime(), msg, self.address, self.port)
        BasicSafeSession.interpret(self, msg)

    def send(self, message, send_unverified=False):
        """ Send given message if connection was verified or send_unverified option is set to True.
        :param Message message: message to be sent.
        :param boolean send_unverified: should message be sent even if the connection hasn't been verified yet?
        """
        BasicSafeSession.send(self, message, send_unverified)
        self.p2p_service.setLastMessage("->", self.key_id, time.localtime(), message, self.address, self.port)

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
        return self.p2p_service.verifySig(msg.sig, msg.get_short_hash(), self.key_id)

    def encrypt(self, data):
        """ Encrypt given data using key_id from this connection.
        :param str data: serialized message to be encrypted
        :return str: encrypted message
        """
        return self.p2p_service.encrypt(data, self.key_id)

    def decrypt(self, data):
        """
        Decrypt given data using private key. If during decryption AssertionError occured this may mean that
        data is not encrypted simple serialized message. In that case unaltered data are returned.
        :param str data: data to be decrypted
        :return str msg: decrypted message
        """
        if not self.p2p_service:
            return data

        try:
            msg = self.p2p_service.decrypt(data)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
            msg = data
        except Exception as err:
            logger.error("Failed to decrypt message {}".format(str(err)))
            assert False

        return msg

    def start(self):
        """
        Send first hello message
        """
        logger.info("Starting peer session {} : {}".format(self.address, self.port))
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
         :param uuid task_id: task to be removed
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
        :param uuid node_id: send opinion about node with this id
        :param LocalRank loc_rank: opinion bout node
        :return:
        """
        self.send(MessageLocRank(node_id, loc_rank))

    def send_find_node(self, node_id):
        """ Send find node message
        :param str node_id: key of a node to be find """
        self.send(MessageFindNode(node_id))

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
        :param Node node_info: information about requester
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
        self._sendPong()

    def _react_to_pong(self, msg):
        self.p2p_service.pongReceived(self.node_id, self.key_id, self.address, self.port)

    def _react_to_hello(self, msg):
        self.node_id = msg.client_uid
        self.node_info = msg.node_info
        self.key_id = msg.client_key_id
        self.listen_port = msg.port

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(PeerSession.DCRUnverified)
            return

        enough_peers = self.p2p_service.enoughPeers()
        p = self.p2p_service.findPeer(self.node_id)

        self.p2p_service.addToPeerKeeper(self.node_id, self.key_id, self.address, self.listen_port, self.node_info)

        if enough_peers:
            logger_msg = "TOO MANY PEERS, DROPPING CONNECTION: {} {}: {}".format(self.node_id, self.address, self.port)
            logger.info(logger_msg)
            nodes_info = self.p2p_service.findNode(self.p2p_service.getKeyId())
            self.send(MessagePeers(nodes_info))
            self.disconnect(PeerSession.DCRTooManyPeers)
            return

        if p and p != self and p.conn.opened:
            # self.sendPing()
            logger_msg = "PEER DUPLICATED: {} {} : {}".format(p.node_id, p.address, p.port)
            logger.warning("{} AND {} : {}".format(logger_msg, msg.client_uid, msg.port))
            self.disconnect(PeerSession.DCRDuplicatePeers)

        if not p:
            self.p2p_service.addPeer(self.node_id, self)
            self.__send_hello()
            self.send(MessageRandVal(msg.rand_val), send_unverified=True)

        # print "Add peer to client uid:{} address:{} port:{}".format(self.node_id, self.address, self.port)

    def _react_to_get_peers(self, msg):
        self.__send_peers()

    def _react_to_peers(self, msg):
        peers_info = msg.peers_array
        self.degree = len(peers_info)
        for pi in peers_info:
            self.p2p_service.tryToAddPeer(pi)

    def _react_to_get_tasks(self, msg):
        tasks = self.p2p_service.getTasksHeaders()
        self.__send_tasks(tasks)

    def _react_to_tasks(self, msg):
        for t in msg.tasks_array:
            if not self.p2p_service.addTaskHeader(t):
                self.disconnect(PeerSession.DCRBadProtocol)

    def _react_to_remove_task(self, msg):
        self.p2p_service.removeTaskHeader(msg.task_id)

    def _react_to_get_resource_peers(self, msg):
        self.__send_resource_peers()

    def _react_to_resource_peers(self, msg):
        self.p2p_service.setResourcePeers(msg.resource_peers)

    def _react_to_degree(self, msg):
        self.degree = msg.degree

    def _react_to_gossip(self, msg):
        self.p2p_service.hearGossip(msg.gossip)

    def _react_to_stop_gossip(self, msg):
        self.p2p_service.stopGossip(self.node_id)

    def _react_to_loc_rank(self, msg):
        self.p2p_service.safeNeighbourLocRank(self.node_id, msg.node_id, msg.loc_rank)

    def _react_to_find_node(self, msg):
        nodes_info = self.p2p_service.findNode(msg.node_key_id)
        self.send(MessagePeers(nodes_info))

    def _react_to_rand_val(self, msg):
        if self.rand_val == msg.rand_val:
            self.verified = True
            self.p2p_service.setSuggestedAddr(self.key_id, self.address, self.port)

    def _react_to_want_to_start_task_session(self, msg):
        self.p2p_service.peerWantTaskSession(msg.node_info, msg.super_node_info, msg.conn_id)

    def _react_to_set_task_session(self, msg):
        self.p2p_service.peerWantToSetTaskSession(msg.key_id, msg.node_info, msg.conn_id, msg.super_node_info)

    def _react_to_nat_hole(self, msg):
        self.p2p_service.traverseNat(msg.key_id, msg.addr, msg.port, msg.conn_id, self.key_id)

    def _react_to_nat_traverse_failure(self, msg):
        self.p2p_service.traverseNatFailure(msg.conn_id)

    def _react_to_inform_about_nat_traverse_failure(self, msg):
        self.p2p_service.sendNatTraverseFailure(msg.key_id, msg.conn_id)

    def __send_hello(self):
        listen_params = self.p2p_service.getListenParams()
        listen_params += (self.rand_val,)
        self.send(MessageHello(*listen_params), send_unverified=True)

    def __send_ping(self):
        self.send(MessagePing())

    def __send_pong(self):
        self.send(MessagePong())

    def __send_peers(self):
        peers_info = []
        for p in self.p2p_service.peers.values():
            peers_info.append({
                "address": p.address,
                "port": p.listen_port,
                "id": p.node_id,
                "node": p.node_info
            })
        self.send(MessagePeers(peers_info))

    def __send_tasks(self, tasks):
        self.send(MessageTasks(tasks))

    def __send_resource_peers(self):
        resource_peers = self.p2p_service.getResourcePeers()
        self.send(MessageResourcePeers(resource_peers))

    def __set_msg_interpretations(self):
        self.__set_basic_msg_interpretations()
        self.__set_resource_msg_interpretations()
        self.__set_ranking_msg_interpretations()

    def __set_basic_msg_interpretations(self):
        self._interpretation.update({
            MessagePing.Type: self._react_to_ping,
            MessagePong.Type: self._react_to_pong,
            MessageHello.Type: self._react_to_hello,
            MessageGetPeers.Type: self._react_to_get_peers,
            MessagePeers.Type: self._react_to_peers,
            MessageGetTasks.Type: self._react_to_get_tasks,
            MessageTasks.Type: self._react_to_tasks,
            MessageRemoveTask.Type: self._react_to_remove_task,
            MessageFindNode.Type: self._react_to_find_node,
            MessageRandVal.Type: self._react_to_rand_val,
            MessageWantToStartTaskSession.Type: self._react_to_want_to_start_task_session,
            MessageSetTaskSession.Type: self._react_to_set_task_session,
            MessageNatHole.Type: self._react_to_nat_hole,
            MessageNatTraverseFailure.Type: self._react_to_nat_traverse_failure,
            MessageInformAboutNatTraverseFailure.Type: self._react_to_inform_about_nat_traverse_failure
        })

    def __set_resource_msg_interpretations(self):
        self._interpretation.update({
            MessageGetResourcePeers.Type: self._react_to_get_resource_peers,
            MessageResourcePeers.Type: self._react_to_resource_peers,
        })

    def __set_ranking_msg_interpretations(self):
        self._interpretation.update({
            MessageDegree.Type: self._react_to_degree,
            MessageGossip.Type: self._react_to_gossip,
            MessageLocRank.Type: self._react_to_loc_rank,
            MessageStopGossip.Type: self._react_to_stop_gossip,
        })
