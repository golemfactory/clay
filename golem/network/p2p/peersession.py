from golem_messages import message
import logging
from pydispatch import dispatcher
import semantic_version
import time
import random

from golem.appconfig import SEND_PEERS_NUM
from golem.core import variables
from golem.core.crypto import ECIESDecryptionError
from golem.network.transport.session import BasicSafeSession
from golem.network.transport.tcpnetwork import SafeProtocol

logger = logging.getLogger(__name__)


def compare_version(client_ver):
    try:
        v_client = semantic_version.Version(client_ver)
    except ValueError:
        logger.debug('Received invalid version tag: %r', client_ver)
        return
    if semantic_version.Version(variables.APP_VERSION) < v_client:
        dispatcher.send(
            signal='golem.p2p',
            event='new_version',
            version=v_client,
        )


class PeerSessionInfo(object):
    attributes = [
        'address', 'port',
        'verified', 'degree', 'key_id',
        'node_name', 'node_info',
        'listen_port', 'conn_id', 'client_ver'
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

    def __init__(self, conn):
        """
        Create new session
        :param Protocol conn: connection protocol implementation that this
                              session should enhance
        :return None:
        """
        BasicSafeSession.__init__(self, conn)
        self.p2p_service = self.conn.server

        # Information about peer
        self.degree = 0
        self.node_name = ""
        self.node_info = None
        self.client_ver = None
        self.listen_port = None
        self.conn_id = None

        # Verification by challenge not a random value
        self.solve_challenge = False
        self.challenge = None
        self.difficulty = 0

        self.can_be_unverified.extend(
            [
                message.Hello.TYPE,
                message.RandVal.TYPE,
                message.ChallengeSolution.TYPE
            ]
        )
        self.can_be_unsigned.extend([message.Hello.TYPE])
        self.can_be_not_encrypted.extend([message.Hello.TYPE])

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
        """React to specific message. Disconnect, if message type is unknown
           for that session.
        Inform p2p service about last message.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        self.p2p_service.set_last_message(
            "<-",
            self.key_id,
            time.localtime(),
            msg,
            self.address,
            self.port
        )
        BasicSafeSession.interpret(self, msg)

    def send(self, msg, send_unverified=False):
        """Send given message if connection was verified or send_unverified
           option is set to True.
        :param Message message: message to be sent.
        :param boolean send_unverified: should message be sent even if
                                        the connection hasn't been
                                        verified yet?
        """
        BasicSafeSession.send(self, msg, send_unverified)
        self.p2p_service.set_last_message(
            "->",
            self.key_id,
            time.localtime(),
            msg,
            self.address,
            self.port
        )

    def sign(self, data):
        """ Sign given bytes
        :param Message data: data to be signed
        :return Message: signed data
        """
        if self.p2p_service is None:
            logger.error("P2PService is None, can't sign a message.")
            return None

        return self.p2p_service.sign(data)

    def verify(self, msg):
        """Verify signature on given message. Check if message was signed
           with key_id from this connection.
        :param Message msg: message to be verified
        :return boolean: True if message was signed with key_id from this
                         connection
        """
        return self.p2p_service.verify_sig(
            msg.sig,
            msg.get_short_hash(),
            self.key_id
        )

    def encrypt(self, data):
        """ Encrypt given data using key_id from this connection.
        :param str data: serialized message to be encrypted
        :return str: encrypted message
        """
        return self.p2p_service.encrypt(data, self.key_id)

    def decrypt(self, data):
        """Decrypt given data using private key. If during decryption
           AssertionError occurred this may mean that data is not encrypted
           simple serialized message. In that case unaltered data are returned.
        :param str data: data to be decrypted
        :return str msg: decrypted message
        """
        if not self.p2p_service:
            return data

        try:
            msg = self.p2p_service.decrypt(data)
        except ECIESDecryptionError as err:
            logger.info(
                "Failed to decrypt message from %r:%r,"
                " maybe it's not encrypted? %r",
                self.address,
                self.port,
                err
            )
            msg = data

        return msg

    def start(self):
        """
        Send first hello message
        """
        if self.conn_type is None:
            raise Exception('Connection type (client/server) unknown')
        logger.info(
            "Starting peer session %r:%r",
            self.address,
            self.port
        )
        if self.__should_init_handshake():
            self.__send_hello()

    def ping(self, interval):
        """Will send ping message if time from last message was longer
           than interval
        :param float interval: number of seconds that should pass until
                               ping message may be send
        """
        if time.time() - self.last_message_time > interval:
            self.__send_ping()

    def send_get_peers(self):
        """  Send get peers message """
        self.send(message.GetPeers())

    def send_get_tasks(self):
        """  Send get tasks message """
        self.send(message.GetTasks())

    def send_remove_task(self, task_id):
        """  Send remove task  message
         :param str task_id: task to be removed
        """
        self.send(message.RemoveTask(task_id=task_id))

    def send_get_resource_peers(self):
        """ Send get resource peers message """
        self.send(message.GetResourcePeers())

    def send_degree(self, degree):
        """ Send degree message
         :param int degree: degree of this node
        """
        self.send(message.Degree(degree=degree))

    def send_gossip(self, gossip):
        """ Send message with gossip
         :param list gossip: gossip to be send
        """
        self.send(message.Gossip(gossip))

    def send_stop_gossip(self):
        """ Send stop gossip message """
        self.send(message.StopGossip())

    def send_loc_rank(self, node_id, loc_rank):
        """ Send local opinion about given node
        :param node_id: send opinion about node with this id
        :param LocalRank loc_rank: opinion bout node
        :return:
        """
        self.send(message.LocRank(node_id=node_id, loc_rank=loc_rank))

    def send_find_node(self, key_num):
        """ Send find node message
        :param long key_num: key of a node to be find """
        self.send(message.FindNode(node_key_id=key_num))

    def send_want_to_start_task_session(
            self,
            node_info,
            conn_id,
            super_node_info
    ):
        """ Send request for starting task session with given node
        :param Node node_info: information about this node.
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        """
        self.send(
            message.WantToStartTaskSession(
                node_info=node_info,
                conn_id=conn_id,
                super_node_info=super_node_info
            )
        )

    def send_set_task_session(
            self,
            key_id,
            node_info,
            conn_id,
            super_node_info
    ):
        """Send information that node from node_info want to start task
           session with key_id node
        :param key_id: target node key
        :param Node node_info: information about requestor
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        """
        self.send(
            message.SetTaskSession(
                key_id=key_id,
                node_info=node_info,
                conn_id=conn_id,
                super_node_info=super_node_info
            )
        )

    def __should_init_handshake(self):
        return self.conn_type == self.CONN_TYPE_SERVER

    def _react_to_ping(self, msg):
        self._send_pong()

    def _react_to_pong(self, msg):
        self.p2p_service.pong_received(self.key_id)

    def _react_to_hello(self, msg):
        if self.verified:
            logger.error("Received unexpected Hello message, ignoring")
            return
        self.node_name = msg.node_name
        self.node_info = msg.node_info
        self.client_ver = msg.client_ver
        self.listen_port = msg.port
        self.key_id = msg.client_key_id

        metadata = msg.metadata
        solve_challenge = msg.solve_challenge
        challenge = msg.challenge
        difficulty = msg.difficulty

        # Check if sender is a seed/bootstrap node
        if (self.address, msg.port) in self.p2p_service.seeds:
            compare_version(msg.client_ver)

        if msg.proto_id != variables.PROTOCOL_CONST.P2P_ID:
            logger.info(
                "P2P protocol version mismatch %r vs %r (local)"
                " for node %r:%r",
                msg.proto_id,
                variables.PROTOCOL_CONST.P2P_ID,
                self.address,
                self.port
            )
            self.disconnect(message.Disconnect.REASON.ProtocolVersion)
            return

        self.p2p_service.add_to_peer_keeper(self.node_info)
        self.p2p_service.interpret_metadata(metadata,
                                            self.address,
                                            self.listen_port,
                                            self.node_info)

        p = self.p2p_service.find_peer(self.key_id)

        if p:
            if p != self and p.conn.opened:
                # self.sendPing()
                logger_msg = "PEER DUPLICATED: %r %r : %r AND %r : %r"
                logger.warning(
                    logger_msg,
                    p.node_name,
                    p.address,
                    p.port,
                    msg.node_name,
                    msg.port
                )
                self.disconnect(message.Disconnect.REASON.DuplicatePeers)
                return

            if solve_challenge and not self.verified:
                self._solve_challenge(challenge, difficulty)
        else:
            if not self.__should_init_handshake():
                self.__send_hello()
            if solve_challenge:
                self._solve_challenge(challenge, difficulty)
            else:
                self.send(message.RandVal(rand_val=msg.rand_val))

    def _solve_challenge(self, challenge, difficulty):
        solution = self.p2p_service.solve_challenge(
            self.key_id,
            challenge,
            difficulty
        )
        self.send(message.ChallengeSolution(solution=solution))

    def _react_to_get_peers(self, msg):
        self._send_peers()

    def _react_to_peers(self, msg):
        if not isinstance(msg.peers, list):
            return

        peers_info = msg.peers[:SEND_PEERS_NUM]
        self.degree = len(peers_info)
        for pi in peers_info:
            self.p2p_service.try_to_add_peer(pi)

    def _react_to_get_tasks(self, msg):
        tasks = self.p2p_service.get_tasks_headers()
        if not tasks:
            return
        if len(tasks) > variables.TASK_HEADERS_LIMIT:
            tasks_to_send = random.sample(tasks, variables.TASK_HEADERS_LIMIT)
            self.send(message.Tasks(tasks_to_send))
        else:
            self.send(message.Tasks(tasks))

    def _react_to_tasks(self, msg):
        for t in msg.tasks:
            if not self.p2p_service.add_task_header(t):
                self.disconnect(
                    message.Disconnect.REASON.BadProtocol
                )

    def _react_to_remove_task(self, msg):
        self.p2p_service.remove_task_header(msg.task_id)

    def _react_to_get_resource_peers(self, msg):
        resource_peers = self.p2p_service.get_resource_peers()
        self.send(message.ResourcePeers(resource_peers=resource_peers))

    def _react_to_resource_peers(self, msg):
        self.p2p_service.set_resource_peers(msg.resource_peers)

    def _react_to_degree(self, msg):
        self.degree = msg.degree

    def _react_to_gossip(self, msg):
        self.p2p_service.hear_gossip(msg.gossip)

    def _react_to_stop_gossip(self, msg):
        self.p2p_service.stop_gossip(self.key_id)

    def _react_to_loc_rank(self, msg):
        self.p2p_service.safe_neighbour_loc_rank(
            self.key_id,
            msg.node_id,
            msg.loc_rank
        )

    def _react_to_find_node(self, msg):
        self._send_peers(node_key_id=msg.node_key_id)

    def _react_to_rand_val(self, msg):
        # if self.solve_challenge:
        #    return
        if self.rand_val == msg.rand_val:
            self.__set_verified_conn()
        else:
            self.disconnect(
                message.Disconnect.REASON.Unverified
            )

    def _react_to_challenge_solution(self, msg):
        if not self.solve_challenge:
            self.disconnect(
                message.Disconnect.REASON.BadProtocol
            )
            return
        good_solution = self.p2p_service.check_solution(
            msg.solution,
            self.challenge,
            self.difficulty
        )
        if good_solution:
            self.__set_verified_conn()
            self.solve_challenge = False
        else:
            self.disconnect(
                message.Disconnect.REASON.Unverified
            )

    def _react_to_want_to_start_task_session(self, msg):
        self.p2p_service.peer_want_task_session(
            msg.node_info,
            msg.super_node_info,
            msg.conn_id
        )

    def _react_to_set_task_session(self, msg):
        self.p2p_service.want_to_start_task_session(
            msg.key_id,
            msg.node_info,
            msg.conn_id,
            msg.super_node_info
        )

    def _react_to_disconnect(self, msg):
        super(PeerSession, self)._react_to_disconnect(msg)

    def _send_pong(self):
        self.send(message.Pong())

    def __send_hello(self):
        self.solve_challenge = self.key_id and \
            self.p2p_service.should_solve_challenge or False
        challenge_kwargs = {}
        if self.solve_challenge:
            challenge = self.p2p_service._get_challenge(self.key_id)
            self.challenge = challenge_kwargs['challenge'] = challenge
            difficulty = self.p2p_service._get_difficulty(self.key_id)
            self.difficulty = challenge_kwargs['difficulty'] = difficulty
        msg = message.Hello(
            proto_id=variables.PROTOCOL_CONST.P2P_ID,
            port=self.p2p_service.cur_port,
            node_name=self.p2p_service.node_name,
            client_key_id=self.p2p_service.keys_auth.get_key_id(),
            node_info=self.p2p_service.node,
            client_ver=variables.APP_VERSION,
            rand_val=self.rand_val,
            metadata=self.p2p_service.metadata_manager.get_metadata(),
            solve_challenge=self.solve_challenge,
            **challenge_kwargs
        )
        self.send(msg, send_unverified=True)

    def __send_ping(self):
        self.send(message.Ping())

    def _send_peers(self, node_key_id=None):
        nodes_info = self.p2p_service.find_node(node_key_id=node_key_id,
                                                alpha=SEND_PEERS_NUM)
        self.send(message.Peers(nodes_info))

    def __set_verified_conn(self):
        self.verified = True

        if self.p2p_service.enough_peers():
            logger_msg = "TOO MANY PEERS, DROPPING CONNECTION: {} {}: {}" \
                .format(self.node_name, self.address, self.port)
            logger.info(logger_msg)
            self._send_peers(node_key_id=self.p2p_service.get_key_id())
            self.disconnect(message.Disconnect.REASON.TooManyPeers)

            self.p2p_service.try_to_add_peer({"address": self.address,
                                              "port": self.listen_port,
                                              "node": self.node_info,
                                              "node_name": self.node_name,
                                              "conn_trials": 0})
            return

        self.p2p_service.add_peer(self.key_id, self)
        self.p2p_service.verified_conn(self.conn_id)
        self.p2p_service.add_known_peer(
            self.node_info,
            self.address,
            self.port
        )
        self.p2p_service.set_suggested_address(
            self.key_id,
            self.address,
            self.port
        )

    def __set_msg_interpretations(self):
        self.__set_basic_msg_interpretations()
        self.__set_resource_msg_interpretations()
        self.__set_ranking_msg_interpretations()

    def __set_basic_msg_interpretations(self):
        self._interpretation.update({
            message.Ping.TYPE: self._react_to_ping,
            message.Pong.TYPE: self._react_to_pong,
            message.Hello.TYPE: self._react_to_hello,
            message.ChallengeSolution.TYPE: self._react_to_challenge_solution,
            message.GetPeers.TYPE: self._react_to_get_peers,
            message.Peers.TYPE: self._react_to_peers,
            message.GetTasks.TYPE: self._react_to_get_tasks,
            message.Tasks.TYPE: self._react_to_tasks,
            message.RemoveTask.TYPE: self._react_to_remove_task,
            message.FindNode.TYPE: self._react_to_find_node,
            message.RandVal.TYPE: self._react_to_rand_val,
            message.WantToStartTaskSession.TYPE: self._react_to_want_to_start_task_session,  # noqa
            message.SetTaskSession.TYPE: self._react_to_set_task_session,
        })

    def __set_resource_msg_interpretations(self):
        self._interpretation.update({
            message.GetResourcePeers.TYPE: self._react_to_get_resource_peers,
            message.ResourcePeers.TYPE: self._react_to_resource_peers,
        })

    def __set_ranking_msg_interpretations(self):
        self._interpretation.update({
            message.Gossip.TYPE: self._react_to_gossip,
            message.LocRank.TYPE: self._react_to_loc_rank,
            message.StopGossip.TYPE: self._react_to_stop_gossip,
        })
