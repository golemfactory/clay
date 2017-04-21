import abc
import collections
import logging
import time
import warnings

from golem.core.databuffer import DataBuffer
from golem.core.simplehash import SimpleHash
from golem.core.simpleserializer import CBORSerializer

logger = logging.getLogger(__name__)


class Message(object):
    """ Communication message that is sent in all networks """

    registered_message_types = {}  # Message types that are allowed to be sent in the network """

    def __init__(self, sig="", timestamp=None):
        """ Create new message. If this message type hasn't been registered yet, add this class to registered message
        collection. """
        if self.TYPE not in Message.registered_message_types:
            Message.registered_message_types[self.TYPE] = self.__class__

        self.sig = sig  # signature (short data representation signed with private key)
        if timestamp is None:
            timestamp = time.time()
        self.timestamp = timestamp
        self.encrypted = False  # inform if message was encrypted

    def get_short_hash(self):
        """ Return short message representation for signature
        :return str: short hash of serialized and sorted message dictionary representation """
        sorted_dict = self._sort_obj(self.dict_repr())
        return SimpleHash.hash(CBORSerializer.dumps(sorted_dict))

    def _sort_obj(self, v):
        if isinstance(v, dict):
            return self._sort_dict(v)
        # treat objects as dictionaries
        elif hasattr(v, '__dict__'):
            return self._sort_dict(v.__dict__, filter_properties=True)
        elif isinstance(v, basestring):
            return self._unicode(v)
        elif isinstance(v, collections.Iterable):
            return v.__class__([self._sort_obj(_v) for _v in v])
        return v

    def _sort_dict(self, dictionary, filter_properties=False):
        result = dict()
        for k, v in dictionary.iteritems():
            if filter_properties and (k.startswith('_') or callable(v)):
                continue
            result[self._unicode(k)] = self._sort_obj(v)
        return sorted(result.items())

    @staticmethod
    def _unicode(value):
        if value is None:
            return None
        try:
            return unicode(value)
        except UnicodeDecodeError:
            return value

    def serialize(self):
        """ Return serialized message
        :return str: serialized message """
        try:
            return CBORSerializer.dumps([self.TYPE, self.sig, self.timestamp, self.dict_repr()])
        except Exception:
            logger.exception("Error serializing message:")
            raise

    def serialize_to_buffer(self, db_):
        """
        Append serialized message to given data buffer
        :param DataBuffer db_: data buffer that message should be attached to
        """
        if not isinstance(db_, DataBuffer):
            raise TypeError("Incorrect db type: {}. Should be: DataBuffer".format(db_))
        db_.append_len_prefixed_string(self.serialize())

    @classmethod
    def decrypt_and_deserialize(cls, db_, server):
        """
        Take out messages from data buffer, decrypt them using server if they are encrypted and deserialize them
        :param DataBuffer db_: data buffer containing messages
        :param SafeServer server: server that is able to decrypt data
        :return list: list of decrypted and deserialized messages
        """
        if not isinstance(db_, DataBuffer):
            raise TypeError("Incorrect db type: {}. Should be: DataBuffer".format(db_))
        messages_ = []

        for msg in db_.get_len_prefixed_string():

            encrypted = True
            try:
                msg = server.decrypt(msg)
            except AssertionError:
                logger.info("Failed to decrypt message, maybe it's not encrypted?")
                encrypted = False
            except Exception as err:
                logger.info("Failed to decrypt message {}".format(str(err)))
                continue

            m = cls.deserialize_message(msg)

            if m is None:
                logger.info("Failed to deserialize message {}".format(msg))
                continue

            m.encrypted = encrypted
            messages_.append(m)

        return messages_

    @classmethod
    def deserialize(cls, db_):
        """
        Take out messages from data buffer and deserialize them
        :param DataBuffer db_: data buffer containing messages
        :return list: list of deserialized messages
        """
        if not isinstance(db_, DataBuffer):
            raise TypeError("Incorrect db type: {}. Should be: DataBuffer".format(db_))
        messages_ = []
        msg_ = db_.read_len_prefixed_string()

        while msg_:
            m = cls.deserialize_message(msg_)

            if m:
                messages_.append(m)
            else:
                logger.error("Failed to deserialize message {}".format(msg_))

            msg_ = db_.read_len_prefixed_string()

        return messages_

    @classmethod
    def deserialize_message(cls, msg_):
        """
        Deserialize single message
        :param str msg_: serialized message
        :return Message|None: deserialized message or none if this message type is unknown
        """
        try:
            msg_repr = CBORSerializer.loads(msg_)
        except Exception as exc:
            logger.error("Error deserializing message: {}".format(exc))
            msg_repr = None

        if isinstance(msg_repr, list) and len(msg_repr) >= 4:

            msg_type = msg_repr[0]
            msg_sig = msg_repr[1]
            msg_timestamp = msg_repr[2]
            d_repr = msg_repr[3]

            if msg_type in cls.registered_message_types:
                return cls.registered_message_types[msg_type](sig=msg_sig, timestamp=msg_timestamp, dict_repr=d_repr)

        return None

    @abc.abstractmethod
    def dict_repr(self):
        """
        Returns dictionary/list representation of  any subclass message
        """
        return

    def __str__(self):
        return "{}".format(self.__class__)

    def __repr__(self):
        return "{}".format(self.__class__)


class MessageRedefined(Message):
    """New style Message."""

    def __init__(self, **kwargs):
        self.load_dict_repr(kwargs.pop('dict_repr', None))
        super(MessageRedefined, self).__init__(**kwargs)

    def load_dict_repr(self, dict_repr):
        if dict_repr is None:
            return
        for attr_name in self.MAPPING:
            k = self.MAPPING[attr_name]
            setattr(self, attr_name, dict_repr[k])

    def dict_repr(self):
        return dict((self.MAPPING[attr_name], getattr(self, attr_name)) for attr_name in self.MAPPING)


##################
# Basic Messages #
##################


class MessageHello(Message):
    TYPE = 0

    PROTO_ID_STR = u"PROTO_ID"
    CLI_VER_STR = u"CLI_VER"
    PORT_STR = u"PORT"
    NODE_NAME_STR = u"NODE_NAME"
    CLIENT_KEY_ID_STR = u"CLIENT_KEY_ID"
    RAND_VAL_STR = u"RAND_VAL"
    NODE_INFO_STR = u"NODE_INFO"
    SOLVE_CHALLENGE_STR = u"SOLVE_CHALLENGE"
    CHALLENGE_STR = u"CHALLENGE"
    DIFFICULTY_STR = u"DIFFICULTY"
    METADATA_STR = u"METADATA"

    def __init__(self, port=0, node_name=None, client_key_id=None, node_info=None,
                 rand_val=0, metadata=None, solve_challenge=False, challenge=None, difficulty=0, proto_id=0,
                 client_ver=0, sig="", timestamp=None, dict_repr=None):
        """
        Create new introduction message
        :param int port: listening port
        :param str node_name: uid
        :param str client_key_id: public key
        :param NodeInfo node_info: information about node
        :param float rand_val: random value that should be signed by other site
        :param metadata dict_repr: metadata
        :param boolean solve_challenge: should other client solve given challenge
        :param str challenge: challenge to solve
        :param int difficulty: difficulty of a challenge
        :param int proto_id: protocol id
        :param str client_ver: application version
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        super(MessageHello, self).__init__(sig, timestamp)

        self.proto_id = proto_id
        self.client_ver = client_ver
        self.port = port
        self.node_name = node_name
        self.client_key_id = client_key_id
        self.rand_val = rand_val
        self.node_info = node_info
        self.solve_challenge = solve_challenge
        self.challenge = challenge
        self.difficulty = difficulty
        self.metadata = metadata

        if dict_repr:
            self.proto_id = dict_repr[self.PROTO_ID_STR]
            self.client_ver = dict_repr[self.CLI_VER_STR]
            self.port = dict_repr[self.PORT_STR]
            self.node_name = dict_repr[self.NODE_NAME_STR]
            self.client_key_id = dict_repr[self.CLIENT_KEY_ID_STR]
            self.rand_val = dict_repr[self.RAND_VAL_STR]
            self.node_info = dict_repr[self.NODE_INFO_STR]
            self.challenge = dict_repr[self.CHALLENGE_STR]
            self.solve_challenge = dict_repr[self.SOLVE_CHALLENGE_STR]
            self.difficulty = dict_repr[self.DIFFICULTY_STR]
            self.metadata = dict_repr[self.METADATA_STR]

    def dict_repr(self):
        return {self.PROTO_ID_STR: self.proto_id,
                self.CLI_VER_STR: self.client_ver,
                self.PORT_STR: self.port,
                self.NODE_NAME_STR: self.node_name,
                self.CLIENT_KEY_ID_STR: self.client_key_id,
                self.RAND_VAL_STR: self.rand_val,
                self.NODE_INFO_STR: self.node_info,
                self.SOLVE_CHALLENGE_STR: self.solve_challenge,
                self.CHALLENGE_STR: self.challenge,
                self.DIFFICULTY_STR: self.difficulty,
                self.METADATA_STR: self.metadata
                }


class MessageRandVal(Message):
    TYPE = 1

    RAND_VAL_STR = u"RAND_VAL"

    def __init__(self, rand_val=0, sig="", timestamp=None, dict_repr=None):
        """
        Create a message with signed random value.
        :param float rand_val: random value received from other side
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.rand_val = rand_val

        if dict_repr:
            self.rand_val = dict_repr[self.RAND_VAL_STR]

    def dict_repr(self):
        return {self.RAND_VAL_STR: self.rand_val}


class MessageDisconnect(Message):
    TYPE = 2

    DISCONNECT_REASON_STR = u"DISCONNECT_REASON"

    def __init__(self, reason=-1, sig="", timestamp=None, dict_repr=None):
        """
        Create a disconnect message
        :param int reason: disconnection reason
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.reason = reason

        if dict_repr:
            self.reason = dict_repr[self.DISCONNECT_REASON_STR]

    def dict_repr(self):
        return {self.DISCONNECT_REASON_STR: self.reason}


class MessageChallengeSolution(Message):
    TYPE = 3

    SOLUTION_STR = u"SOLUTION"

    def __init__(self, solution="", sig="", timestamp=None, dict_repr=None):
        """
        Create a message with signed cryptographic challenge solution
        :param str solution: challenge solution
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.solution = solution

        if dict_repr:
            self.solution = dict_repr[self.SOLUTION_STR]

    def dict_repr(self):
        return {self.SOLUTION_STR: self.solution}


################
# P2P Messages #
################

P2P_MESSAGE_BASE = 1000


class MessagePing(Message):
    TYPE = P2P_MESSAGE_BASE + 1

    PING_STR = u"PING"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create ping message
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if not dict_repr.get(self.PING_STR):
                raise IOError("Ping message failed")

    def dict_repr(self):
        return {self.PING_STR: True}


class MessagePong(Message):
    TYPE = P2P_MESSAGE_BASE + 2

    PONG_STR = u"PONG"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create pong message
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.PONG_STR) is None:
                raise IOError("Pong message failed")

    def dict_repr(self):
        return {self.PONG_STR: True}


class MessageGetPeers(Message):
    TYPE = P2P_MESSAGE_BASE + 3

    GET_PEERS_STR = u"GET_PEERS"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create request peers message
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.GET_PEERS_STR) is None:
                raise IOError("Get peers message failed")

    def dict_repr(self):
        return {self.GET_PEERS_STR: True}


class MessagePeers(Message):
    TYPE = P2P_MESSAGE_BASE + 4

    PEERS_STR = u"PEERS"

    def __init__(self, peers_array=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message containing information about peers
        :param list peers_array: list of peers information
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if peers_array is None:
            peers_array = []

        self.peers_array = peers_array

        if dict_repr:
            self.peers_array = dict_repr[self.PEERS_STR]

    def dict_repr(self):
        return {self.PEERS_STR: self.peers_array}


class MessageGetTasks(Message):
    TYPE = P2P_MESSAGE_BASE + 5

    GET_TASKS_STR = u"GET_TASKS"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """ Create request task message
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.GET_TASKS_STR) is None:
                raise IOError("Get tasks message failed")

    def dict_repr(self):
        return {self.GET_TASKS_STR: True}


class MessageTasks(Message):
    TYPE = P2P_MESSAGE_BASE + 6

    TASKS_STR = u"TASKS"

    def __init__(self, tasks_array=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message containing information about tasks
        :param list tasks_array: list of peers information
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if tasks_array is None:
            tasks_array = []

        self.tasks_array = tasks_array

        if dict_repr:
            self.tasks_array = dict_repr[self.TASKS_STR]

    def dict_repr(self):
        return {self.TASKS_STR: self.tasks_array}


class MessageRemoveTask(Message):
    TYPE = P2P_MESSAGE_BASE + 7

    REMOVE_TASK_STR = u"REMOVE_TASK"

    def __init__(self, task_id=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with request to remove given task
        :param str task_id: task to be removed
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.task_id = task_id

        if dict_repr:
            self.task_id = dict_repr[self.REMOVE_TASK_STR]

    def dict_repr(self):
        return {self.REMOVE_TASK_STR: self.task_id}


class MessageGetResourcePeers(Message):
    TYPE = P2P_MESSAGE_BASE + 8

    WANT_RESOURCE_PEERS_STR = u"WANT_RESOURCE_PEERS"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create request for resource peers
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.WANT_RESOURCE_PEERS_STR) is None:
                raise IOError("Get resource peers message failed")

    def dict_repr(self):
        return {self.WANT_RESOURCE_PEERS_STR: True}


class MessageResourcePeers(Message):
    TYPE = P2P_MESSAGE_BASE + 9

    RESOURCE_PEERS_STR = u"RESOURCE_PEERS"

    def __init__(self, resource_peers=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message containing information about resource peers
        :param list resource_peers: list of peers information
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if resource_peers is None:
            resource_peers = []

        self.resource_peers = resource_peers

        if dict_repr:
            self.resource_peers = dict_repr[self.RESOURCE_PEERS_STR]

    def dict_repr(self):
        return {self.RESOURCE_PEERS_STR: self.resource_peers}


class MessageDegree(Message):
    TYPE = P2P_MESSAGE_BASE + 10

    DEGREE_STR = u"DEGREE"

    def __init__(self, degree=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about node degree
        :param int degree: node degree in golem network
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.degree = degree

        if dict_repr:
            self.degree = dict_repr[self.DEGREE_STR]

    def dict_repr(self):
        return {self.DEGREE_STR: self.degree}


class MessageGossip(Message):
    TYPE = P2P_MESSAGE_BASE + 11

    GOSSIP_STR = u"GOSSIP"

    def __init__(self, gossip=None, sig="", timestamp=None, dict_repr=None):
        """
        Create gossip message
        :param list gossip: gossip to be send
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.gossip = gossip

        if dict_repr:
            self.gossip = dict_repr[self.GOSSIP_STR]

    def dict_repr(self):
        return {self.GOSSIP_STR: self.gossip}


class MessageStopGossip(Message):
    TYPE = P2P_MESSAGE_BASE + 12

    STOP_GOSSIP_STR = u"STOP_GOSSIP"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """ Create stop gossip message
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.STOP_GOSSIP_STR) is None:
                raise IOError("Stop gossip message failed")

    def dict_repr(self):
        return {self.STOP_GOSSIP_STR: True}


class MessageLocRank(Message):
    TYPE = P2P_MESSAGE_BASE + 13

    NODE_ID_STR = u"NODE_ID"
    LOC_RANK_STR = u"LOC_RANK"

    def __init__(self, node_id='', loc_rank='', sig="", timestamp=None, dict_repr=None):
        """
        Create message with local opinion about given node
        :param uuid node_id: message contain opinion about node with this id
        :param LocalRank loc_rank: opinion about node
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.node_id = node_id
        self.loc_rank = loc_rank

        if dict_repr:
            self.node_id = dict_repr[self.NODE_ID_STR]
            self.loc_rank = dict_repr[self.LOC_RANK_STR]

    def dict_repr(self):
        return {self.NODE_ID_STR: self.node_id,
                self.LOC_RANK_STR: self.loc_rank}


class MessageFindNode(Message):
    TYPE = P2P_MESSAGE_BASE + 14

    NODE_KEY_ID_STR = u"NODE_KEY_ID"

    def __init__(self, node_key_id='', sig="", timestamp=None, dict_repr=None):
        """
        Create find node message
        :param str node_key_id: key of a node to be find
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.node_key_id = node_key_id

        if dict_repr:
            self.node_key_id = dict_repr[self.NODE_KEY_ID_STR]

    def dict_repr(self):
        return {self.NODE_KEY_ID_STR: self.node_key_id}


class MessageWantToStartTaskSession(Message):
    TYPE = P2P_MESSAGE_BASE + 15

    NODE_INFO_STR = u"NODE_INFO"
    CONN_ID_STR = u"CONN_ID"
    SUPER_NODE_INFO_STR = u"SUPER_NODE_INFO"

    def __init__(self, node_info=None, conn_id=None, super_node_info=None, sig="", timestamp=None,
                 dict_repr=None):
        """
        Create request for starting task session with given node
        :param Node node_info: information about this node
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.node_info = node_info
        self.conn_id = conn_id
        self.super_node_info = super_node_info

        if dict_repr:
            self.node_info = dict_repr[self.NODE_INFO_STR]
            self.conn_id = dict_repr[self.CONN_ID_STR]
            self.super_node_info = dict_repr[self.SUPER_NODE_INFO_STR]

    def dict_repr(self):
        return {
            self.NODE_INFO_STR: self.node_info,
            self.CONN_ID_STR: self.conn_id,
            self.SUPER_NODE_INFO_STR: self.super_node_info
        }


class MessageSetTaskSession(Message):
    TYPE = P2P_MESSAGE_BASE + 16

    KEY_ID_STR = u"KEY_ID"
    NODE_INFO_STR = u"NODE_INFO"
    CONN_ID_STR = u"CONN_ID"
    SUPER_NODE_INFO_STR = u"SUPER_NODE_INFO"

    def __init__(self, key_id=None, node_info=None, conn_id=None, super_node_info=None, sig="", timestamp=None,
                 dict_repr=None):
        """
        Create message with information that node from node_info want to start task session with key_id node
        :param key_id: target node key
        :param Node node_info: information about requestor
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.key_id = key_id
        self.node_info = node_info
        self.conn_id = conn_id
        self.super_node_info = super_node_info

        if dict_repr:
            self.key_id = dict_repr[self.KEY_ID_STR]
            self.node_info = dict_repr[self.NODE_INFO_STR]
            self.conn_id = dict_repr[self.CONN_ID_STR]
            self.super_node_info = dict_repr[self.SUPER_NODE_INFO_STR]

    def dict_repr(self):
        return {
            self.KEY_ID_STR: self.key_id,
            self.NODE_INFO_STR: self.node_info,
            self.CONN_ID_STR: self.conn_id,
            self.SUPER_NODE_INFO_STR: self.super_node_info
        }


class MessageNatHole(Message):
    TYPE = P2P_MESSAGE_BASE + 17

    KEY_ID_STR = u"KEY_ID"
    ADDR_STR = u"ADDR"
    PORT_STR = u"PORT"
    CONN_ID_STR = u"CONN_ID"

    def __init__(self, key_id=None, addr=None, port=None, conn_id=None, sig="", timestamp=None,
                 dict_repr=None):
        """
        Create message with information about nat hole
        :param key_id: key of the node behind nat hole
        :param str addr: address of the nat hole
        :param int port: port of the nat hole
        :param uuid conn_id: connection id for reference
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.key_id = key_id
        self.addr = addr
        self.port = port
        self.conn_id = conn_id

        if dict_repr:
            self.key_id = dict_repr[self.KEY_ID_STR]
            self.addr = dict_repr[self.ADDR_STR]
            self.port = dict_repr[self.PORT_STR]
            self.conn_id = dict_repr[self.CONN_ID_STR]

    def dict_repr(self):
        return {
            self.KEY_ID_STR: self.key_id,
            self.ADDR_STR: self.addr,
            self.PORT_STR: self.port,
            self.CONN_ID_STR: self.conn_id
        }


class MessageNatTraverseFailure(Message):
    TYPE = P2P_MESSAGE_BASE + 18

    CONN_ID_STR = u"CONN_ID"

    def __init__(self, conn_id=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about unsuccessful nat traverse
        :param uuid conn_id: connection id for reference
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.conn_id = conn_id

        if dict_repr:
            self.conn_id = dict_repr[self.CONN_ID_STR]

    def dict_repr(self):
        return {
            self.CONN_ID_STR: self.conn_id
        }


class MessageInformAboutNatTraverseFailure(Message):
    TYPE = P2P_MESSAGE_BASE + 19

    KEY_ID_STR = u"KEY_ID"
    CONN_ID_STR = u"CONN_ID"

    def __init__(self, key_id=None, conn_id=None, sig="", timestamp=None, dict_repr=None):
        """
        Create request to inform node with key_id about unsuccessful nat traverse.
        :param key_id: key of the node that should be inform about failure
        :param uuid conn_id: connection id for reference
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.key_id = key_id
        self.conn_id = conn_id

        if dict_repr:
            self.key_id = dict_repr[self.KEY_ID_STR]
            self.conn_id = dict_repr[self.CONN_ID_STR]

    def dict_repr(self):
        return {
            self.KEY_ID_STR: self.key_id,
            self.CONN_ID_STR: self.conn_id
        }


TASK_MSG_BASE = 2000


class MessageWantToComputeTask(Message):
    TYPE = TASK_MSG_BASE + 1

    NODE_NAME_STR = u"NODE_NAME"
    TASK_ID_STR = u"TASK_ID"
    PERF_INDEX_STR = u"PERF_INDEX"
    MAX_RES_STR = u"MAX_RES"
    MAX_MEM_STR = u"MAX_MEM"
    NUM_CORES_STR = u"NUM_CORES"
    PRICE_STR = u"PRICE"

    def __init__(self, node_name=0, task_id=0, perf_index=0, price=0, max_resource_size=0, max_memory_size=0,
                 num_cores=0, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that node wants to compute given task
        :param str node_name: id of that node
        :param uuid task_id: if of a task that node wants to compute
        :param float perf_index: benchmark result for this task type
        :param int max_resource_size: how much disk space can this node offer
        :param int max_memory_size: how much ram can this node offer
        :param int num_cores: how many cpu cores this node can offer
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.node_name = node_name
        self.task_id = task_id
        self.perf_index = perf_index
        self.max_resource_size = max_resource_size
        self.max_memory_size = max_memory_size
        self.num_cores = num_cores
        self.price = price

        if dict_repr:
            self.node_name = dict_repr[self.NODE_NAME_STR]
            self.task_id = dict_repr[self.TASK_ID_STR]
            self.perf_index = dict_repr[self.PERF_INDEX_STR]
            self.max_resource_size = dict_repr[self.MAX_RES_STR]
            self.max_memory_size = dict_repr[self.MAX_MEM_STR]
            self.num_cores = dict_repr[self.NUM_CORES_STR]
            self.price = dict_repr[self.PRICE_STR]

    def dict_repr(self):
        return {self.NODE_NAME_STR: self.node_name,
                self.TASK_ID_STR: self.task_id,
                self.PERF_INDEX_STR: self.perf_index,
                self.MAX_RES_STR: self.max_resource_size,
                self.MAX_MEM_STR: self.max_memory_size,
                self.NUM_CORES_STR: self.num_cores,
                self.PRICE_STR: self.price}


class MessageTaskToCompute(Message):
    TYPE = TASK_MSG_BASE + 2

    COMPUTE_TASK_DEF_STR = u"COMPUTE_TASK_DEF"

    def __init__(self, ctd=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about subtask to compute
        :param ComputeTaskDef ctd: definition of a subtask that should be computed
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.ctd = ctd

        if dict_repr:
            self.ctd = dict_repr[self.COMPUTE_TASK_DEF_STR]

    def dict_repr(self):
        return {self.COMPUTE_TASK_DEF_STR: self.ctd}


class MessageCannotAssignTask(Message):
    TYPE = TASK_MSG_BASE + 3

    REASON_STR = u"REASON"
    TASK_ID_STR = u"TASK_ID"

    def __init__(self, task_id=0, reason="", sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that node can't get task to compute
        :param task_id: task that cannot be assigned
        :param str reason: reason why task cannot be assigned to asking node
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.task_id = task_id
        self.reason = reason

        if dict_repr:
            self.task_id = dict_repr[self.TASK_ID_STR]
            self.reason = dict_repr[self.REASON_STR]

    def dict_repr(self):
        return {self.TASK_ID_STR: self.task_id,
                self.REASON_STR: self.reason}


class MessageReportComputedTask(Message):
    # FIXME this message should be simpler
    TYPE = TASK_MSG_BASE + 4

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    RESULT_TYPE_STR = u"RESULT_TYPE"
    COMPUTATION_TIME_STR = u"COMPUTATION_TIME"
    NODE_NAME_STR = u"NODE_NAME"
    ADDR_STR = u"ADDR"
    NODE_INFO_STR = u"NODE_INFO"
    PORT_STR = u"PORT"
    KEY_ID_STR = u"KEY_ID"
    EXTRA_DATA_STR = u"EXTRA_DATA"
    ETH_ACCOUNT_STR = u"ETH_ACCOUNT"

    def __init__(self, subtask_id=0, result_type=None, computation_time='', node_name='', address='',
                 port='', key_id='', node_info=None, eth_account='', extra_data=None,
                 sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about finished computation
        :param str subtask_id: finished subtask id
        :param int result_type: type of a result (from result_types dict)
        :param float computation_time: how long does it take to  compute this subtask
        :param node_name: task result owner name
        :param str address: task result owner address
        :param int port: task result owner port
        :param key_id: task result owner key
        :param Node node_info: information about this node
        :param str eth_account: ethereum address (bytes20) of task result owner
        :param extra_data: additional information, eg. list of files
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id
        self.result_type = result_type
        self.extra_data = extra_data
        self.computation_time = computation_time
        self.node_name = node_name
        self.address = address
        self.port = port
        self.key_id = key_id
        self.eth_account = eth_account
        self.node_info = node_info

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]
            self.result_type = dict_repr[self.RESULT_TYPE_STR]
            self.computation_time = dict_repr[self.COMPUTATION_TIME_STR]
            self.node_name = dict_repr[self.NODE_NAME_STR]
            self.address = dict_repr[self.ADDR_STR]
            self.port = dict_repr[self.PORT_STR]
            self.key_id = dict_repr[self.KEY_ID_STR]
            self.eth_account = dict_repr[self.ETH_ACCOUNT_STR]
            self.extra_data = dict_repr[self.EXTRA_DATA_STR]
            self.node_info = dict_repr[self.NODE_INFO_STR]

    def dict_repr(self):
        return {self.SUB_TASK_ID_STR: self.subtask_id,
                self.RESULT_TYPE_STR: self.result_type,
                self.COMPUTATION_TIME_STR: self.computation_time,
                self.NODE_NAME_STR: self.node_name,
                self.ADDR_STR: self.address,
                self.PORT_STR: self.port,
                self.KEY_ID_STR: self.key_id,
                self.ETH_ACCOUNT_STR: self.eth_account,
                self.EXTRA_DATA_STR: self.extra_data,
                self.NODE_INFO_STR: self.node_info}


class MessageGetTaskResult(Message):
    TYPE = TASK_MSG_BASE + 5

    SUB_TASK_ID_STR = u"SUB_TASK_ID"

    def __init__(self, subtask_id="", sig="", timestamp=None, dict_repr=None):
        """
        Create request for task result
        :param str subtask_id: finished subtask id
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]

    def dict_repr(self):
        return {self.SUB_TASK_ID_STR: self.subtask_id}


# It's an old form of sending task result (don't use if it isn't necessary)
class MessageTaskResult(Message):
    TYPE = TASK_MSG_BASE + 6

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    RESULT_STR = u"RESULT"

    def __init__(self, subtask_id=0, result=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with task results
        :param str subtask_id: id of finished subtask
        :param result: task result in binary form
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        warnings.warn("It's an old form of sending task result (don't use if it isn't necessary)", DeprecationWarning)
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id
        self.result = result

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]
            self.result = dict_repr[self.RESULT_STR]

    def dict_repr(self):
        return {self.SUB_TASK_ID_STR: self.subtask_id,
                self.RESULT_STR: self.result}


class MessageTaskResultHash(Message):
    TYPE = TASK_MSG_BASE + 7

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    MULTIHASH_STR = u"MULTIHASH"
    SECRET_STR = u"SECRET"
    OPTIONS_STR = u"OPTIONS"

    def __init__(self, subtask_id=0, multihash="", secret="", options=None, sig="", timestamp=None, dict_repr=None):

        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id
        self.multihash = multihash
        self.secret = secret
        self.options = options

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]
            self.multihash = dict_repr[self.MULTIHASH_STR]
            self.secret = dict_repr[self.SECRET_STR]
            self.options = dict_repr[self.OPTIONS_STR]

    def dict_repr(self):
        return {self.SUB_TASK_ID_STR: self.subtask_id,
                self.MULTIHASH_STR: self.multihash,
                self.SECRET_STR: self.secret,
                self.OPTIONS_STR: self.options}


class MessageGetResource(Message):
    TYPE = TASK_MSG_BASE + 8

    TASK_ID_STR = u"SUB_TASK_ID"
    RESOURCE_HEADER_STR = u"RESOURCE_HEADER"

    def __init__(self, task_id="", resource_header=None, sig="", timestamp=None, dict_repr=None):
        """
        Send request for resource to given task
        :param uuid task_id: given task id
        :param ResourceHeader resource_header: description of resources that current node has
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.task_id = task_id
        self.resource_header = resource_header

        if dict_repr:
            self.task_id = dict_repr[self.TASK_ID_STR]
            self.resource_header = dict_repr[self.RESOURCE_HEADER_STR]

    def dict_repr(self):
        return {self.TASK_ID_STR: self.task_id,
                self.RESOURCE_HEADER_STR: self.resource_header
                }


# Old method of sending resource. Don't use if it isn't necessary.
class MessageResource(Message):
    TYPE = TASK_MSG_BASE + 9

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    RESOURCE_STR = u"RESOURCE"

    def __init__(self, subtask_id=0, resource=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with resource
        :param str subtask_id: attached resource is needed for this subtask computation
        :param resource: resource in binary for
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        warnings.warn("Old method of sending resource. Don't use if it isn't necessary.", DeprecationWarning)
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id
        self.resource = resource

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]
            self.resource = dict_repr[self.RESOURCE_STR]

    def dict_repr(self):
        return {self.SUB_TASK_ID_STR: self.subtask_id,
                self.RESOURCE_STR: self.resource
                }


class MessageSubtaskResultAccepted(Message):
    TYPE = TASK_MSG_BASE + 10

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    REWARD_STR = u"REWARD"

    def __init__(self, subtask_id=0, reward=0, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that subtask result was accepted
        :param str subtask_id: accepted subtask id
        :param float reward: payment for computations
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id
        self.reward = reward

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]
            self.reward = dict_repr[self.REWARD_STR]

    def dict_repr(self):
        return {
            self.SUB_TASK_ID_STR: self.subtask_id,
            self.REWARD_STR: self.reward
        }


class MessageSubtaskResultRejected(Message):
    TYPE = TASK_MSG_BASE + 11

    SUB_TASK_ID_STR = u"SUB_TASK_ID"

    def __init__(self, subtask_id=0, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that subtask result was rejected
        :param str subtask_id: id of rejected subtask
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id

        if dict_repr:
            self.subtask_id = dict_repr[self.SUB_TASK_ID_STR]

    def dict_repr(self):
        return {
            self.SUB_TASK_ID_STR: self.subtask_id
        }


class MessageDeltaParts(Message):
    TYPE = TASK_MSG_BASE + 12

    TASK_ID_STR = u"TASK_ID"
    DELTA_HEADER_STR = u"DELTA_HEADER"
    PARTS_STR = u"PARTS"
    NODE_NAME_STR = u"NODE_NAME"
    ADDR_STR = u"ADDR"
    PORT_STR = u"PORT"
    NODE_INFO_STR = u"node info"

    def __init__(self, task_id=0, delta_header=None, parts=None, node_name='',
                 node_info=None, addr='', port='', sig="", timestamp=None,
                 dict_repr=None):
        """
        Create message with resource description in form of "delta parts".
        :param task_id: resources are for task with this id
        :param TaskResourceHeader delta_header: resource header containing only parts that computing node doesn't have
        :param list parts: list of all files that are needed to create resources
        :param str node_name: resource owner name
        :param Node node_info: information about resource owner
        :param addr: resource owner address
        :param port: resource owner port
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.task_id = task_id
        self.delta_header = delta_header
        self.parts = parts
        self.node_name = node_name
        self.addr = addr
        self.port = port
        self.node_info = node_info

        if dict_repr:
            self.task_id = dict_repr[self.TASK_ID_STR]
            self.delta_header = dict_repr[self.DELTA_HEADER_STR]
            self.parts = dict_repr[self.PARTS_STR]
            self.node_name = dict_repr[self.NODE_NAME_STR]
            self.addr = dict_repr[self.ADDR_STR]
            self.port = dict_repr[self.PORT_STR]
            self.node_info = dict_repr[self.NODE_INFO_STR]

    def dict_repr(self):
        return {
            self.TASK_ID_STR: self.task_id,
            self.DELTA_HEADER_STR: self.delta_header,
            self.PARTS_STR: self.parts,
            self.NODE_NAME_STR: self.node_name,
            self.ADDR_STR: self.addr,
            self.PORT_STR: self.port,
            self.NODE_INFO_STR: self.node_info
        }


class MessageResourceFormat(Message):
    TYPE = TASK_MSG_BASE + 13

    USE_DISTRIBUTED_RESOURCE_STR = u"USE_DISTRIBUTED_RESOURCE"

    def __init__(self, use_distributed_resource=0, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about resource format
        :param bool use_distributed_resource: false if resource will be sent directly, true if resource should be pulled
            from network  with resource server
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.use_distributed_resource = use_distributed_resource

        if dict_repr:
            self.use_distributed_resource = dict_repr[self.USE_DISTRIBUTED_RESOURCE_STR]

    def dict_repr(self):
        return {
            self.USE_DISTRIBUTED_RESOURCE_STR: self.use_distributed_resource
        }


class MessageAcceptResourceFormat(Message):
    TYPE = TASK_MSG_BASE + 14

    ACCEPT_RESOURCE_FORMAT_STR = u"ACCEPT_RESOURCE_FORMAT"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create message with resource format confirmation
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.ACCEPT_RESOURCE_FORMAT_STR) is None:
                raise IOError("Accept resource format message failed")

    def dict_repr(self):
        return {self.ACCEPT_RESOURCE_FORMAT_STR: True}


class MessageTaskFailure(Message):
    TYPE = TASK_MSG_BASE + 15

    SUBTASK_ID_STR = u"SUBTASK_ID"
    ERR_STR = u"ERR"

    def __init__(self, subtask_id="", err="", sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about task computation failure
        :param str subtask_id: id of a failed subtask
        :param str err: error message that occur during computations
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.subtask_id = subtask_id
        self.err = err

        if dict_repr:
            self.subtask_id = dict_repr[self.SUBTASK_ID_STR]
            self.err = dict_repr[self.ERR_STR]

    def dict_repr(self):
        return {
            self.SUBTASK_ID_STR: self.subtask_id,
            self.ERR_STR: self.err
        }


class MessageStartSessionResponse(Message):
    TYPE = TASK_MSG_BASE + 16

    CONN_ID_STR = u"CONN_ID"

    def __init__(self, conn_id=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that this session was started as an answer for a request to start task session
        :param uuid conn_id: connection id for reference
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.conn_id = conn_id

        if dict_repr:
            self.conn_id = dict_repr[self.CONN_ID_STR]

    def dict_repr(self):
        return {self.CONN_ID_STR: self.conn_id}


class MessageMiddleman(Message):
    TYPE = TASK_MSG_BASE + 17

    ASKING_NODE_STR = u"ASKING_NODE"
    DEST_NODE_STR = u"DEST_NODE"
    ASK_CONN_ID_STR = u"ASK_CONN_ID"

    def __init__(self, asking_node=None, dest_node=None, ask_conn_id=None, sig="", timestamp=None,
                 dict_repr=None):
        """
        Create message that is used to ask node to become middleman in the communication with other node
        :param Node asking_node: other node information. Middleman should connect with that node.
        :param Node dest_node: information about this node
        :param ask_conn_id: connection id that asking node gave for reference
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.asking_node = asking_node
        self.dest_node = dest_node
        self.ask_conn_id = ask_conn_id

        if dict_repr:
            self.asking_node = dict_repr[self.ASKING_NODE_STR]
            self.dest_node = dict_repr[self.DEST_NODE_STR]
            self.ask_conn_id = dict_repr[self.ASK_CONN_ID_STR]

    def dict_repr(self):
        return {
            self.ASKING_NODE_STR: self.asking_node,
            self.DEST_NODE_STR: self.dest_node,
            self.ASK_CONN_ID_STR: self.ask_conn_id
        }


class MessageJoinMiddlemanConn(Message):
    TYPE = TASK_MSG_BASE + 18

    CONN_ID_STR = u"CONN_ID"
    KEY_ID_STR = u"KEY_ID"
    DEST_NODE_KEY_ID_STR = u"DEST_NODE_KEY_ID"

    def __init__(self, key_id=None, conn_id=None, dest_node_key_id=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message that is used to ask node communicate with other through middleman connection (this node
        is the middleman and connection with other node is already opened
        :param key_id:  this node public key
        :param conn_id: connection id for reference
        :param dest_node_key_id: public key of the other node of the middleman connection
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.conn_id = conn_id
        self.key_id = key_id
        self.dest_node_key_id = dest_node_key_id

        if dict_repr:
            self.conn_id = dict_repr[self.CONN_ID_STR]
            self.key_id = dict_repr[self.KEY_ID_STR]
            self.dest_node_key_id = dict_repr[self.DEST_NODE_KEY_ID_STR]

    def dict_repr(self):
        return {self.CONN_ID_STR: self.conn_id,
                self.KEY_ID_STR: self.key_id,
                self.DEST_NODE_KEY_ID_STR: self.dest_node_key_id}


class MessageBeingMiddlemanAccepted(Message):
    TYPE = TASK_MSG_BASE + 19

    MIDDLEMAN_STR = u"MIDDLEMAN"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that node accepted being a middleman
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.MIDDLEMAN_STR) is None:
                raise IOError("Being middleman accept message failed")

    def dict_repr(self):
        return {self.MIDDLEMAN_STR: True}


class MessageMiddlemanAccepted(Message):
    TYPE = TASK_MSG_BASE + 20

    MIDDLEMAN_STR = u"MIDDLEMAN"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that this node accepted connection with middleman.
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.MIDDLEMAN_STR) is None:
                raise IOError("Middleman accept message failed")

    def dict_repr(self):
        return {self.MIDDLEMAN_STR: True}


class MessageMiddlemanReady(Message):
    TYPE = TASK_MSG_BASE + 21

    MIDDLEMAN_STR = u"MIDDLEMAN"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that other node connected and middleman session may be started
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.MIDDLEMAN_STR) is None:
                raise IOError("Middleman ready message failed")

    def dict_repr(self):
        return {self.MIDDLEMAN_STR: True}


class MessageNatPunch(Message):
    TYPE = TASK_MSG_BASE + 22

    ASKING_NODE_STR = u"ASKING_NODE"
    DEST_NODE_STR = u"DEST_NODE"
    ASK_CONN_ID_STR = u"ASK_CONN_ID"

    def __init__(self, asking_node=None, dest_node=None, ask_conn_id=None, sig="", timestamp=None,
                 dict_repr=None):
        """
        Create message that is used to ask node to inform other node about nat hole that this node will prepare
        with this connection
        :param Node asking_node: node that should be informed about potential hole based on this connection
        :param Node dest_node: node that will try to end this connection and open hole in it's NAT
        :param uuid ask_conn_id: connection id that asking node gave for reference
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.asking_node = asking_node
        self.dest_node = dest_node
        self.ask_conn_id = ask_conn_id

        if dict_repr:
            self.asking_node = dict_repr[self.ASKING_NODE_STR]
            self.dest_node = dict_repr[self.DEST_NODE_STR]
            self.ask_conn_id = dict_repr[self.ASK_CONN_ID_STR]

    def dict_repr(self):
        return {
            self.ASKING_NODE_STR: self.asking_node,
            self.DEST_NODE_STR: self.dest_node,
            self.ASK_CONN_ID_STR: self.ask_conn_id
        }


class MessageWaitForNatTraverse(Message):
    TYPE = TASK_MSG_BASE + 23

    PORT_STR = u"PORT"

    def __init__(self, port=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message that inform node that it should start listening on given port (to open nat hole)
        :param int port: this connection goes out from this port, other node should listen on this port
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.port = port

        if dict_repr:
            self.port = dict_repr[self.PORT_STR]

    def dict_repr(self):
        return {self.PORT_STR: self.port}


class MessageNatPunchFailure(Message):
    TYPE = TASK_MSG_BASE + 24

    NAT_PUNCH_FAILURE_STR = u"NAT_PUNCH_FAILURE"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Create message that informs node about unsuccessful nat punch
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.NAT_PUNCH_FAILURE_STR) is None:
                raise IOError("Nat punch failure message failed")

    def dict_repr(self):
        return {self.NAT_PUNCH_FAILURE_STR: True}


class MessageWaitingForResults(Message):
    TYPE = TASK_MSG_BASE + 25

    WAITING_FOR_RESULTS_STR = u"WAITING_FOR_RESULTS"

    def __init__(self, sig="", timestamp=None, dict_repr=None):
        """
        Message informs that the node is waiting for results
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        if dict_repr:
            if dict_repr.get(self.WAITING_FOR_RESULTS_STR) is None:
                raise IOError("Waiting for results message failed")

    def dict_repr(self):
        return {self.WAITING_FOR_RESULTS_STR: True}


class MessageCannotComputeTask(Message):
    TYPE = TASK_MSG_BASE + 26

    REASON_STR = u"REASON"
    SUBTASK_ID_STR = u"SUBTASK_ID"

    def __init__(self, subtask_id=None, reason=None, sig="", timestamp=None, dict_repr=None):
        """
        Message informs that the node is waiting for results
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)

        self.reason = reason
        self.subtask_id = subtask_id

        if dict_repr:
            self.reason = dict_repr[self.REASON_STR]
            self.subtask_id = dict_repr[self.SUBTASK_ID_STR]

    def dict_repr(self):
        return {self.REASON_STR: self.reason,
                self.SUBTASK_ID_STR: self.subtask_id}


class MessageSubtaskPayment(MessageRedefined):
    TYPE = TASK_MSG_BASE + 27

    MAPPING = {
        'subtask_id': 'SUB_TASK_ID',
        'reward': 'REWARD_STR',
        'transaction_id': 'TRANSACTION_ID',
    }

    def __init__(self, subtask_id=None, reward=None, transaction_id=None, **kwargs):
        """Informs about payment for a subtask.
        It succeeds MessageSubtaskResultAccepted but could
        be sent after a delay. It is also sent in response to
        MessageSubtaskPaymentRequest. If transaction_id is None it
        should be interpreted as PAYMENT PENDING status.

        :param str subtask_id: accepted subtask id
        :param float reward: payment for computations
        :param str transaction_id: eth transaction id
        :param dict dict_repr: dictionary representation of a message

        Additional params are described in Message().
        """

        self.subtask_id = subtask_id
        self.reward = reward
        self.transaction_id = transaction_id
        super(MessageSubtaskPayment, self).__init__(**kwargs)


class MessageSubtaskPaymentRequest(MessageRedefined):
    TYPE = TASK_MSG_BASE + 28

    MAPPING = {
        'subtask_id': 'SUB_TASK_ID',
    }

    def __init__(self, subtask_id=None, **kwargs):
        """Requests information about payment for a subtask.

        :param str subtask_id: accepted subtask id
        :param dict dict_repr: dictionary representation of a message

        Additional params are described in Message().
        """

        self.subtask_id = subtask_id
        super(MessageSubtaskPaymentRequest, self).__init__(**kwargs)


RESOURCE_MSG_BASE = 3000


class MessagePushResource(Message):
    TYPE = RESOURCE_MSG_BASE + 1

    RESOURCE_STR = u"resource"
    COPIES_STR = u"copies"

    def __init__(self, resource=None, copies=0, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that expected number of copies of given resource should be pushed to the network
        :param str resource: resource name
        :param int copies: number of copies
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)
        self.resource = resource
        self.copies = copies

        if dict_repr:
            self.resource = dict_repr[self.RESOURCE_STR]
            self.copies = dict_repr[self.COPIES_STR]

    def dict_repr(self):
        return {self.RESOURCE_STR: self.resource,
                self.COPIES_STR: self.copies
                }


class MessageHasResource(Message):
    TYPE = RESOURCE_MSG_BASE + 2

    RESOURCE_STR = u"resource"

    def __init__(self, resource=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information about having given resource
        :param str resource: resource name
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)
        self.resource = resource

        if dict_repr:
            self.resource = dict_repr[self.RESOURCE_STR]

    def dict_repr(self):
        return {self.RESOURCE_STR: self.resource}


class MessageWantsResource(Message):
    TYPE = RESOURCE_MSG_BASE + 3

    RESOURCE_STR = u"resource"

    def __init__(self, resource=None, sig="", timestamp=None, dict_repr=None):
        """
        Send information that node want to receive given resource
        :param str resource: resource name
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)
        self.resource = resource

        if dict_repr:
            self.resource = dict_repr[self.RESOURCE_STR]

    def dict_repr(self):
        return {self.RESOURCE_STR: self.resource}


class MessagePullResource(Message):
    TYPE = RESOURCE_MSG_BASE + 4

    RESOURCE_STR = u"resource"

    def __init__(self, resource=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information that given resource is needed
        :param str resource: resource name
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)
        self.resource = resource

        if dict_repr:
            self.resource = dict_repr[self.RESOURCE_STR]

    def dict_repr(self):
        return {self.RESOURCE_STR: self.resource}


class MessagePullAnswer(Message):
    TYPE = RESOURCE_MSG_BASE + 5

    RESOURCE_STR = u"resource"
    HAS_RESOURCE_STR = u"has resource"

    def __init__(self, resource=None, has_resource=False, sig="", timestamp=None, dict_repr=None):
        """
        Create message with information whether current peer has given resource and may send it
        :param str resource: resource name
        :param bool has_resource: information if user has resource
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)
        self.resource = resource
        self.has_resource = has_resource

        if dict_repr:
            self.resource = dict_repr[self.RESOURCE_STR]
            self.has_resource = dict_repr[self.HAS_RESOURCE_STR]

    def dict_repr(self):
        return {self.RESOURCE_STR: self.resource,
                self.HAS_RESOURCE_STR: self.has_resource}


# Old message. Don't use if it isn't necessary.
class MessageSendResource(Message):
    TYPE = RESOURCE_MSG_BASE + 6

    RESOURCE_STR = u"resource"

    def __init__(self, resource=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with resource request
        :param str resource: resource name
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        warnings.warn("Old message. Don't use if it isn't necessary.", DeprecationWarning)
        Message.__init__(self, sig, timestamp)
        self.resource = resource

        if dict_repr:
            self.resource = dict_repr[self.RESOURCE_STR]

    def dict_repr(self):
        return {self.RESOURCE_STR: self.resource}


class MessageResourceList(Message):
    TYPE = RESOURCE_MSG_BASE + 7

    RESOURCES_STR = u"resources"
    OPTIONS_STR = u"options"

    def __init__(self, resources=None, options=None, sig="", timestamp=None, dict_repr=None):
        """
        Create message with resource request
        :param str resources: resource list
        :param str sig: signature
        :param float timestamp: current timestamp
        :param dict dict_repr: dictionary representation of a message
        """
        Message.__init__(self, sig, timestamp)
        self.resources = resources
        self.options = options

        if dict_repr:
            self.resources = dict_repr[self.RESOURCES_STR]
            self.options = dict_repr[self.OPTIONS_STR]

    def dict_repr(self):
        return {self.RESOURCES_STR: self.resources,
                self.OPTIONS_STR: self.options}


def init_messages():
    """Add supported messages to register messages list"""
    # Basic messages
    MessageHello()
    MessageRandVal()
    MessageDisconnect()
    MessageChallengeSolution()

    # P2P messages
    MessagePing()
    MessagePong()
    MessageGetPeers()
    MessageGetTasks()
    MessagePeers()
    MessageTasks()
    MessageRemoveTask()
    MessageFindNode()
    MessageGetResourcePeers()
    MessageResourcePeers()
    MessageWantToStartTaskSession()
    MessageSetTaskSession()
    MessageNatHole()
    MessageNatTraverseFailure()
    MessageInformAboutNatTraverseFailure()
    # Ranking messages
    MessageDegree()
    MessageGossip()
    MessageStopGossip()
    MessageLocRank()

    # Task messages
    MessageCannotAssignTask()
    MessageCannotComputeTask()
    MessageTaskToCompute()
    MessageWantToComputeTask()
    MessageReportComputedTask()
    MessageTaskResult()
    MessageTaskResultHash()
    MessageTaskFailure()
    MessageGetTaskResult()
    MessageStartSessionResponse()
    MessageMiddleman()
    MessageJoinMiddlemanConn()
    MessageBeingMiddlemanAccepted()
    MessageMiddlemanAccepted()
    MessageMiddlemanReady()
    MessageNatPunch()
    MessageWaitForNatTraverse()
    MessageNatPunchFailure()
    MessageWaitingForResults()
    MessageSubtaskResultAccepted()
    MessageSubtaskResultRejected()
    MessageDeltaParts()
    MessageResourceFormat()
    MessageAcceptResourceFormat()

    Message.registered_message_types[MessageSubtaskPayment.TYPE] = MessageSubtaskPayment
    Message.registered_message_types[MessageSubtaskPaymentRequest.TYPE] = MessageSubtaskPaymentRequest

    # Resource messages
    MessageGetResource()
    MessageResource()
    MessagePushResource()
    MessageHasResource()
    MessageWantsResource()
    MessagePullResource()
    MessagePullAnswer()
    MessageSendResource()
    MessageResourceList()
