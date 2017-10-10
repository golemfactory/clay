import logging
import struct
import time


from golem.core.databuffer import DataBuffer
from golem.core.simplehash import SimpleHash
from golem.core.simpleserializer import CBORSerializer
from golem.task.taskbase import ResultType

logger = logging.getLogger('golem.network.transport.message')


# Message types that are allowed to be sent in the network
registered_message_types = {}


class Message(object):
    """ Communication message that is sent in all networks """

    __slots__ = ['timestamp', 'encrypted', 'sig', 'payload', '_raw']

    def __init__(self, timestamp=None, encrypted=False, sig=None,
                 payload=None, raw=None, slots=None):

        """Create a new message
        :param timestamp: message timestamp
        :param encrypted: whether message was encrypted
        :param payload: payload bytes
        :param sig: signed message hash
        :param raw: original message bytes
        """
        if not registered_message_types:
            init_messages()

        self.load_slots(slots)

        # Header
        self.timestamp = timestamp or time.time()
        self.encrypted = encrypted
        self.sig = sig

        self.payload = payload
        self._raw = raw

    @property
    def raw(self):
        return self._raw[:]

    def get_short_hash(self):
        """Return short message representation for signature
        :return bytes: sha1(TYPE, timestamp, encrypted, payload)
        """
        sha = SimpleHash.hash_object()
        sha.update(self.serialize_header())
        sha.update(self.payload or b'')
        return sha.digest()

    def serialize(self, sign_func, encrypt_func=None):
        """ Return serialized message
        :return str: serialized message """
        try:
            self.payload = self.serialize_payload()

            if encrypt_func:
                self.encrypted = True
                self.payload = encrypt_func(self.payload)

            self.sig = sign_func(self.get_short_hash())

            return (
                self.serialize_header() +
                self.sig +
                self.payload
            )

        except Exception:
            logger.exception("Error serializing message:")
            raise

    def serialize_header(self):
        """ Serialize message's header
        I unsigned short (2 bytes) big-endian
        Q unsigned long long (8 bytes) big-endian
        ? bool (1 byte)

        11 bytes in total

        :return: serialized header
        """
        return struct.pack('!HQ?', self.TYPE,
                           int(self.timestamp * 10 ** 6),
                           self.encrypted)

    def serialize_payload(self):
        return CBORSerializer.dumps(self.slots())

    @classmethod
    def deserialize_header(cls, data):
        """ Deserialize message's header

        :param data: bytes
        :return: tuple of (TYPE, timestamp, encrypted)
        """
        assert len(data) == 11
        return struct.unpack('!HQ?', data)

    @classmethod
    def deserialize(cls, db_):
        """
        Take out messages from data buffer and deserialize them
        :param DataBuffer db_: data buffer containing messages
        :return list: list of deserialized messages
        """
        if not isinstance(db_, DataBuffer):
            raise TypeError(
                "Incorrect db type: {}. Should be: DataBuffer"
                .format(db_)
            )
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
    def deserialize_message(cls, msg_, decrypt_func=None):
        """
        Deserialize single message
        :param str msg_: serialized message
        :return Message|None: deserialized message or none if this message
                              type is unknown
        """

        if len(msg_) <= 76:  # len(header) + len(sig) = 11 + 65
            logger.error("Message error: invalid length %d", len(msg_))
            return

        msg_hdr = msg_[:11]
        msg_sig = msg_[11:76]
        msg_payload = msg_[76:]

        try:
            msg_type, msg_ts, msg_enc = cls.deserialize_header(msg_hdr)
            if msg_enc:
                msg_payload = decrypt_func(msg_payload)
            slots = CBORSerializer.loads(msg_payload)
        except Exception as exc:
            logger.error("Message error: invalid data: %r", exc)
            return

        if msg_type not in registered_message_types:
            logger.error('Message error: invalid type %d', msg_type)
            return

        return registered_message_types[msg_type](
            timestamp=msg_ts // 10 ** 6,
            encrypted=msg_enc,
            sig=msg_sig,
            payload=msg_payload,
            raw=msg_,
            slots=slots
        )

    def __str__(self):
        return "{}".format(self.__class__)

    def __repr__(self):
        return "{}".format(self.__class__)

    def load_slots(self, slots):
        if not slots:
            return
        for key, value in slots:
            setattr(self, key, value)

    def slots(self):
        """Returns a list representation of any subclass message"""
        return [
            (attr_name, getattr(self, attr_name))
            for attr_name in self.__slots__
        ]


##################
# Basic Messages #
##################


class MessageHello(Message):
    TYPE = 0

    __slots__ = [
        'proto_id',
        'client_ver',
        'port',
        'node_name',
        'client_key_id',
        'rand_val',
        'node_info',
        'solve_challenge',
        'challenge',
        'difficulty',
        'metadata',
    ] + Message.__slots__

    def __init__(
            self,
            port=0,
            node_name=None,
            client_key_id=None,
            node_info=None,
            rand_val=0,
            metadata=None,
            solve_challenge=False,
            challenge=None,
            difficulty=0,
            proto_id=0,
            client_ver=0,
            **kwargs):
        """
        Create new introduction message
        :param int port: listening port
        :param str node_name: uid
        :param str client_key_id: public key
        :param NodeInfo node_info: information about node
        :param float rand_val: random value that should be signed by other site
        :param metadata dict_repr: metadata
        :param boolean solve_challenge: should other client solve given
                                        challenge
        :param str challenge: challenge to solve
        :param int difficulty: difficulty of a challenge
        :param int proto_id: protocol id
        :param str client_ver: application version
        """

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
        super(MessageHello, self).__init__(**kwargs)


class MessageRandVal(Message):
    TYPE = 1

    __slots__ = ['rand_val'] + Message.__slots__

    def __init__(self, rand_val=0, **kwargs):
        """
        Create a message with signed random value.
        :param float rand_val: random value received from other side
        """
        self.rand_val = rand_val
        super(MessageRandVal, self).__init__(**kwargs)


class MessageDisconnect(Message):
    TYPE = 2

    __slots__ = ['reason'] + Message.__slots__

    def __init__(self, reason=-1, **kwargs):
        """
        Create a disconnect message
        :param int reason: disconnection reason
        """
        self.reason = reason
        super(MessageDisconnect, self).__init__(**kwargs)


class MessageChallengeSolution(Message):
    TYPE = 3

    __slots__ = ['solution'] + Message.__slots__

    def __init__(self, solution="", **kwargs):
        """
        Create a message with signed cryptographic challenge solution
        :param str solution: challenge solution
        """
        self.solution = solution
        super(MessageChallengeSolution, self).__init__(**kwargs)


################
# P2P Messages #
################

P2P_MESSAGE_BASE = 1000


class MessagePing(Message):
    TYPE = P2P_MESSAGE_BASE + 1


class MessagePong(Message):
    TYPE = P2P_MESSAGE_BASE + 2


class MessageGetPeers(Message):
    TYPE = P2P_MESSAGE_BASE + 3


class MessagePeers(Message):
    TYPE = P2P_MESSAGE_BASE + 4

    __slots__ = ['peers_array'] + Message.__slots__

    def __init__(self, peers_array=None, **kwargs):
        """
        Create message containing information about peers
        :param list peers_array: list of peers information
        """
        self.peers_array = peers_array or []
        super(MessagePeers, self).__init__(**kwargs)


class MessageGetTasks(Message):
    TYPE = P2P_MESSAGE_BASE + 5


class MessageTasks(Message):
    TYPE = P2P_MESSAGE_BASE + 6

    __slots__ = ['tasks_array'] + Message.__slots__

    def __init__(self, tasks_array=None, **kwargs):
        """
        Create message containing information about tasks
        :param list tasks_array: list of peers information
        """
        self.tasks_array = tasks_array or []
        super(MessageTasks, self).__init__(**kwargs)


class MessageRemoveTask(Message):
    TYPE = P2P_MESSAGE_BASE + 7

    __slots__ = ['task_id'] + Message.__slots__

    def __init__(self, task_id=None, **kwargs):
        """
        Create message with request to remove given task
        :param str task_id: task to be removed
        """
        self.task_id = task_id
        super(MessageRemoveTask, self).__init__(**kwargs)


class MessageGetResourcePeers(Message):
    """Request for resource peers"""
    TYPE = P2P_MESSAGE_BASE + 8


class MessageResourcePeers(Message):
    TYPE = P2P_MESSAGE_BASE + 9

    __slots__ = ['resource_peers'] + Message.__slots__

    def __init__(self, resource_peers=None, **kwargs):
        """
        Create message containing information about resource peers
        :param list resource_peers: list of peers information
        """
        self.resource_peers = resource_peers or []
        super(MessageResourcePeers, self).__init__(**kwargs)


class MessageDegree(Message):
    TYPE = P2P_MESSAGE_BASE + 10

    __slots__ = ['degree'] + Message.__slots__

    def __init__(self, degree=None, **kwargs):
        """
        Create message with information about node degree
        :param int degree: node degree in golem network
        """
        self.degree = degree
        super(MessageDegree, self).__init__(**kwargs)


class MessageGossip(Message):
    TYPE = P2P_MESSAGE_BASE + 11

    __slots__ = ['gossip'] + Message.__slots__

    def __init__(self, gossip=None, **kwargs):
        """
        Create gossip message
        :param list gossip: gossip to be send
        """
        self.gossip = gossip or []
        super(MessageGossip, self).__init__(**kwargs)


class MessageStopGossip(Message):
    """Create stop gossip message"""
    TYPE = P2P_MESSAGE_BASE + 12


class MessageLocRank(Message):
    TYPE = P2P_MESSAGE_BASE + 13

    __slots__ = ['node_id', 'loc_rank'] + Message.__slots__

    def __init__(self, node_id='', loc_rank='', **kwargs):
        """
        Create message with local opinion about given node
        :param uuid node_id: message contain opinion about node with this id
        :param LocalRank loc_rank: opinion about node
        """
        self.node_id = node_id
        self.loc_rank = loc_rank
        super(MessageLocRank, self).__init__(**kwargs)


class MessageFindNode(Message):
    TYPE = P2P_MESSAGE_BASE + 14

    __slots__ = ['node_key_id'] + Message.__slots__

    def __init__(self, node_key_id='', **kwargs):
        """
        Create find node message
        :param str node_key_id: key of a node to be find
        """
        self.node_key_id = node_key_id
        super(MessageFindNode, self).__init__(**kwargs)


class MessageWantToStartTaskSession(Message):
    TYPE = P2P_MESSAGE_BASE + 15

    __slots__ = [
        'node_info',
        'conn_id',
        'super_node_info'
    ] + Message.__slots__

    def __init__(
            self,
            node_info=None,
            conn_id=None,
            super_node_info=None,
            **kwargs):
        """
        Create request for starting task session with given node
        :param Node node_info: information about this node
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        """
        self.node_info = node_info
        self.conn_id = conn_id
        self.super_node_info = super_node_info
        super(MessageWantToStartTaskSession, self).__init__(**kwargs)


class MessageSetTaskSession(Message):
    TYPE = P2P_MESSAGE_BASE + 16

    __slots__ = [
        'key_id',
        'node_info',
        'conn_id',
        'super_node_info',
    ] + Message.__slots__

    def __init__(
            self,
            key_id=None,
            node_info=None,
            conn_id=None,
            super_node_info=None,
            **kwargs):
        """Create message with information that node from node_info wants
           to start task session with key_id node
        :param key_id: target node key
        :param Node node_info: information about requestor
        :param uuid conn_id: connection id for reference
        :param Node|None super_node_info: information about known supernode
        """
        self.key_id = key_id
        self.node_info = node_info
        self.conn_id = conn_id
        self.super_node_info = super_node_info
        super(MessageSetTaskSession, self).__init__(**kwargs)


class MessageNatHole(Message):
    TYPE = P2P_MESSAGE_BASE + 17

    __slots__ = [
        'key_id',
        'address',
        'port',
        'conn_id'
    ] + Message.__slots__

    def __init__(
            self,
            key_id=None,
            address=None,
            port=None,
            conn_id=None,
            **kwargs):
        """
        Create message with information about nat hole
        :param key_id: key of the node behind nat hole
        :param str address: address of the nat hole
        :param int port: port of the nat hole
        :param uuid conn_id: connection id for reference
        """
        self.key_id = key_id
        self.address = address
        self.port = port
        self.conn_id = conn_id
        super(MessageNatHole, self).__init__(**kwargs)


class MessageNatTraverseFailure(Message):
    TYPE = P2P_MESSAGE_BASE + 18

    __slots__ = ['conn_id'] + Message.__slots__

    def __init__(self, conn_id=None, **kwargs):
        """
        Create message with information about unsuccessful nat traverse
        :param uuid conn_id: connection id for reference
        """
        self.conn_id = conn_id
        super(MessageNatTraverseFailure, self).__init__(**kwargs)


class MessageInformAboutNatTraverseFailure(Message):
    TYPE = P2P_MESSAGE_BASE + 19

    __slots__ = [
        'key_id',
        'conn_id',
    ] + Message.__slots__

    def __init__(self, key_id=None, conn_id=None, **kwargs):
        """Create request to inform node with key_id about unsuccessful
           nat traverse.
        :param key_id: key of the node that should be inform about failure
        :param uuid conn_id: connection id for reference
        """
        self.key_id = key_id
        self.conn_id = conn_id
        super(MessageInformAboutNatTraverseFailure, self).__init__(**kwargs)


TASK_MSG_BASE = 2000


class MessageWantToComputeTask(Message):
    TYPE = TASK_MSG_BASE + 1

    __slots__ = [
        'node_name',
        'task_id',
        'perf_index',
        'max_resource_size',
        'max_memory_size',
        'num_cores',
        'price'
    ] + Message.__slots__

    def __init__(
            self,
            node_name=0,
            task_id=0,
            perf_index=0,
            price=0,
            max_resource_size=0,
            max_memory_size=0,
            num_cores=0,
            **kwargs):
        """
        Create message with information that node wants to compute given task
        :param str node_name: id of that node
        :param uuid task_id: if of a task that node wants to compute
        :param float perf_index: benchmark result for this task type
        :param int max_resource_size: how much disk space can this node offer
        :param int max_memory_size: how much ram can this node offer
        :param int num_cores: how many cpu cores this node can offer
        """
        self.node_name = node_name
        self.task_id = task_id
        self.perf_index = perf_index
        self.max_resource_size = max_resource_size
        self.max_memory_size = max_memory_size
        self.num_cores = num_cores
        self.price = price
        super(MessageWantToComputeTask, self).__init__(**kwargs)


class MessageTaskToCompute(Message):
    TYPE = TASK_MSG_BASE + 2

    __slots__ = ['compute_task_def'] + Message.__slots__

    def __init__(self, compute_task_def=None, **kwargs):
        """
        Create message with information about subtask to compute
        :param ComputeTaskDef compute_task_def: definition of a subtask that
                                                should be computed
        """
        self.compute_task_def = compute_task_def
        super(MessageTaskToCompute, self).__init__(**kwargs)


class MessageCannotAssignTask(Message):
    TYPE = TASK_MSG_BASE + 3

    __slots__ = [
        'reason',
        'task_id'
    ] + Message.__slots__

    def __init__(self, task_id=0, reason="", **kwargs):
        """
        Create message with information that node can't get task to compute
        :param task_id: task that cannot be assigned
        :param str reason: reason why task cannot be assigned to asking node
        """
        self.task_id = task_id
        self.reason = reason
        super(MessageCannotAssignTask, self).__init__(**kwargs)


class MessageReportComputedTask(Message):
    # FIXME this message should be simpler
    TYPE = TASK_MSG_BASE + 4

    __slots__ = [
        'subtask_id',
        'result_type',
        'computation_time',
        'node_name',
        'address',
        'node_info',
        'port',
        'key_id',
        'extra_data',
        'eth_account',
    ] + Message.__slots__

    def __init__(
            self,
            subtask_id=0,
            result_type=ResultType.DATA,
            computation_time='',
            node_name='',
            address='',
            port='',
            key_id='',
            node_info=None,
            eth_account='',
            extra_data=None,
            **kwargs):
        """
        Create message with information about finished computation
        :param str subtask_id: finished subtask id
        :param int result_type: type of a result
        :param float computation_time: how long does it take to  compute this
                                       subtask
        :param node_name: task result owner name
        :param str address: task result owner address
        :param int port: task result owner port
        :param key_id: task result owner key
        :param Node node_info: information about this node
        :param str eth_account: ethereum address (bytes20) of task result owner
        :param extra_data: additional information, eg. list of files
        """
        self.subtask_id = subtask_id
        # TODO why do we need the type here?
        self.result_type = result_type
        self.extra_data = extra_data
        self.computation_time = computation_time
        self.node_name = node_name
        self.address = address
        self.port = port
        self.key_id = key_id
        self.eth_account = eth_account
        self.node_info = node_info
        super().__init__(**kwargs)


class MessageGetTaskResult(Message):
    TYPE = TASK_MSG_BASE + 5

    __slots__ = ['subtask_id'] + Message.__slots__

    def __init__(self, subtask_id="", **kwargs):
        """
        Create request for task result
        :param str subtask_id: finished subtask id
        """
        self.subtask_id = subtask_id
        super(MessageGetTaskResult, self).__init__(**kwargs)


class MessageTaskResultHash(Message):
    TYPE = TASK_MSG_BASE + 7

    __slots__ = [
        'subtask_id',
        'multihash',
        'secret',
        'options'
    ] + Message.__slots__

    def __init__(
            self,
            subtask_id=0,
            multihash="",
            secret="",
            options=None,
            **kwargs):
        self.subtask_id = subtask_id
        self.multihash = multihash
        self.secret = secret
        self.options = options
        super(MessageTaskResultHash, self).__init__(**kwargs)


class MessageGetResource(Message):
    TYPE = TASK_MSG_BASE + 8

    __slots__ = [
        'task_id',
        'resource_header'
    ] + Message.__slots__

    def __init__(self, task_id="", resource_header=None, **kwargs):
        """
        Send request for resource to given task
        :param uuid task_id: given task id
        :param ResourceHeader resource_header: description of resources that
                                               current node has
        """
        self.task_id = task_id
        self.resource_header = resource_header
        super(MessageGetResource, self).__init__(**kwargs)


class MessageSubtaskResultAccepted(Message):
    TYPE = TASK_MSG_BASE + 10

    __slots = [
        'subtask_id',
        'reward'
    ] + Message.__slots__

    def __init__(self, subtask_id=0, reward=0, **kwargs):
        """
        Create message with information that subtask result was accepted
        :param str subtask_id: accepted subtask id
        :param float reward: payment for computations
        """
        self.subtask_id = subtask_id
        self.reward = reward
        super(MessageSubtaskResultAccepted, self).__init__(**kwargs)


class MessageSubtaskResultRejected(Message):
    TYPE = TASK_MSG_BASE + 11

    __slots__ = ['subtask_id'] + Message.__slots__

    def __init__(self, subtask_id=0, **kwargs):
        """
        Create message with information that subtask result was rejected
        :param str subtask_id: id of rejected subtask
        """
        self.subtask_id = subtask_id
        super(MessageSubtaskResultRejected, self).__init__(**kwargs)


class MessageDeltaParts(Message):
    TYPE = TASK_MSG_BASE + 12

    __slots__ = [
        'task_id',
        'delta_header',
        'parts',
        'node_name',
        'address',
        'port',
        'node_info',
    ] + Message.__slots__

    def __init__(self, task_id=0, delta_header=None, parts=None, node_name='',
                 node_info=None, address='', port='', **kwargs):
        """
        Create message with resource description in form of "delta parts".
        :param task_id: resources are for task with this id
        :param TaskResourceHeader delta_header: resource header containing
                                                only parts that computing
                                                node doesn't have
        :param list parts: list of all files that are needed to create
                           resources
        :param str node_name: resource owner name
        :param Node node_info: information about resource owner
        :param address: resource owner address
        :param port: resource owner port
        """
        self.task_id = task_id
        self.delta_header = delta_header
        self.parts = parts
        self.node_name = node_name
        self.address = address
        self.port = port
        self.node_info = node_info
        super(MessageDeltaParts, self).__init__(**kwargs)


class MessageTaskFailure(Message):
    TYPE = TASK_MSG_BASE + 15

    __slots__ = [
        'subtask_id',
        'err'
    ] + Message.__slots__

    def __init__(self, subtask_id="", err="", **kwargs):
        """
        Create message with information about task computation failure
        :param str subtask_id: id of a failed subtask
        :param str err: error message that occur during computations
        """
        self.subtask_id = subtask_id
        self.err = err
        super(MessageTaskFailure, self).__init__(**kwargs)


class MessageStartSessionResponse(Message):
    TYPE = TASK_MSG_BASE + 16

    __slots__ = ['conn_id'] + Message.__slots__

    def __init__(self, conn_id=None, **kwargs):
        """Create message with information that this session was started as
           an answer for a request to start task session
        :param uuid conn_id: connection id for reference
        """
        self.conn_id = conn_id
        super(MessageStartSessionResponse, self).__init__(**kwargs)


class MessageMiddleman(Message):
    TYPE = TASK_MSG_BASE + 17

    __slots__ = [
        'asking_node',
        'dest_node',
        'ask_conn_id'
    ] + Message.__slots__

    def __init__(
            self,
            asking_node=None,
            dest_node=None,
            ask_conn_id=None,
            **kwargs):
        """Create message that is used to ask node to become middleman in the
           communication with other node
        :param Node asking_node: other node information. Middleman should
                                 connect with that node.
        :param Node dest_node: information about this node
        :param ask_conn_id: connection id that asking node gave for reference
        """
        self.asking_node = asking_node
        self.dest_node = dest_node
        self.ask_conn_id = ask_conn_id
        super(MessageMiddleman, self).__init__(**kwargs)


class MessageJoinMiddlemanConn(Message):
    TYPE = TASK_MSG_BASE + 18

    __slots__ = [
        'conn_id',
        'key_id',
        'dest_node_key_id'
    ] + Message.__slots__

    def __init__(
            self,
            key_id=None,
            conn_id=None,
            dest_node_key_id=None,
            **kwargs):
        """Create message that is used to ask node communicate with other
           through middleman connection (this node is the middleman and
           connection with other node is already opened
        :param key_id:  this node public key
        :param conn_id: connection id for reference
        :param dest_node_key_id: public key of the other node of the
                                 middleman connection
        """
        self.conn_id = conn_id
        self.key_id = key_id
        self.dest_node_key_id = dest_node_key_id
        super(MessageJoinMiddlemanConn, self).__init__(**kwargs)


class MessageBeingMiddlemanAccepted(Message):
    """Create message with information that node accepted being a middleman"""
    TYPE = TASK_MSG_BASE + 19


class MessageMiddlemanAccepted(Message):
    """Create message with information that this node accepted connection
       with middleman
    """
    TYPE = TASK_MSG_BASE + 20


class MessageMiddlemanReady(Message):
    """Create message with information that other node connected and
       middleman session may be started
    """
    TYPE = TASK_MSG_BASE + 21


class MessageNatPunch(Message):
    TYPE = TASK_MSG_BASE + 22

    __slots__ = [
        'asking_node',
        'dest_node',
        'ask_conn_id'
    ] + Message.__slots__

    def __init__(
            self,
            asking_node=None,
            dest_node=None,
            ask_conn_id=None,
            **kwargs):
        """Create message that is used to ask node to inform other node about
           nat hole that this node will prepare with this connection
        :param Node asking_node: node that should be informed about potential
                                 hole based on this connection
        :param Node dest_node: node that will try to end this connection and
                               open hole in it's NAT
        :param uuid ask_conn_id: connection id that asking node gave for
                                 reference
        """
        self.asking_node = asking_node
        self.dest_node = dest_node
        self.ask_conn_id = ask_conn_id
        super(MessageNatPunch, self).__init__(**kwargs)


class MessageWaitForNatTraverse(Message):
    TYPE = TASK_MSG_BASE + 23

    __slots__ = ['port'] + Message.__slots__

    def __init__(self, port=None, **kwargs):
        """Create message that inform node that it should start listening on
           given port (to open nat hole)
        :param int port: this connection goes out from this port, other node
                         should listen on this port
        """
        self.port = port
        super(MessageWaitForNatTraverse, self).__init__(**kwargs)


class MessageNatPunchFailure(Message):
    """Create message that informs node about unsuccessful nat punch"""
    TYPE = TASK_MSG_BASE + 24


class MessageWaitingForResults(Message):
    TYPE = TASK_MSG_BASE + 25


class MessageCannotComputeTask(Message):
    TYPE = TASK_MSG_BASE + 26

    __slots__ = [
        'reason',
        'subtask_id'
    ] + Message.__slots__

    def __init__(self, subtask_id=None, reason=None, **kwargs):
        """
        Message informs that the node is waiting for results
        """
        self.reason = reason
        self.subtask_id = subtask_id
        super(MessageCannotComputeTask, self).__init__(**kwargs)


class MessageSubtaskPayment(Message):
    TYPE = TASK_MSG_BASE + 27

    __slots__ = [
        'subtask_id',
        'reward',
        'transaction_id',
        'block_number'
    ] + Message.__slots__

    def __init__(self, subtask_id=None, reward=None, transaction_id=None,
                 block_number=None, **kwargs):
        """Informs about payment for a subtask.
        It succeeds MessageSubtaskResultAccepted but could
        be sent after a delay. It is also sent in response to
        MessageSubtaskPaymentRequest. If transaction_id is None it
        should be interpreted as PAYMENT PENDING status.

        :param str subtask_id: accepted subtask id
        :param float reward: payment for computations
        :param str transaction_id: eth transaction id
        :param int block_number: eth blockNumber
        :param dict dict_repr: dictionary representation of a message

        Additional params are described in Message().
        """

        self.subtask_id = subtask_id
        self.reward = reward
        self.transaction_id = transaction_id
        self.block_number = block_number
        super(MessageSubtaskPayment, self).__init__(**kwargs)


class MessageSubtaskPaymentRequest(Message):
    TYPE = TASK_MSG_BASE + 28

    __slots__ = ['subtask_id'] + Message.__slots__

    def __init__(self, subtask_id=None, **kwargs):
        """Requests information about payment for a subtask.

        :param str subtask_id: accepted subtask id
        :param dict dict_repr: dictionary representation of a message

        Additional params are described in Message().
        """

        self.subtask_id = subtask_id
        super(MessageSubtaskPaymentRequest, self).__init__(**kwargs)


RESOURCE_MSG_BASE = 3000


class AbstractResource(Message):
    __slots__ = ['resource'] + Message.__slots__

    def __init__(self, resource=None, **kwargs):
        """
        :param str resource: resource name
        """
        self.resource = resource
        super(AbstractResource, self).__init__(**kwargs)


class MessagePushResource(AbstractResource):
    TYPE = RESOURCE_MSG_BASE + 1

    __slots__ = [
        'resource',
        'copies'
    ] + Message.__slots__

    def __init__(self, copies=0, **kwargs):
        """Create message with information that expected number of copies of
           given resource should be pushed to the network
        :param int copies: number of copies
        """
        self.copies = copies
        super(MessagePushResource, self).__init__(**kwargs)


class MessageHasResource(AbstractResource):
    """Create message with information about having given resource"""
    TYPE = RESOURCE_MSG_BASE + 2


class MessageWantsResource(AbstractResource):
    """Send information that node wants to receive given resource"""
    TYPE = RESOURCE_MSG_BASE + 3


class MessagePullResource(AbstractResource):
    """Create message with information that given resource is needed"""
    TYPE = RESOURCE_MSG_BASE + 4


class MessagePullAnswer(Message):
    TYPE = RESOURCE_MSG_BASE + 5

    __slots__ = [
        'resource',
        'has_resource'
    ] + Message.__slots__

    def __init__(self, resource=None, has_resource=False, **kwargs):
        """Create message with information whether current peer has given
           resource and may send it
        :param str resource: resource name
        :param bool has_resource: information if user has resource
        """
        self.resource = resource
        self.has_resource = has_resource
        super(MessagePullAnswer, self).__init__(**kwargs)


class MessageResourceList(Message):
    TYPE = RESOURCE_MSG_BASE + 7

    __slots__ = [
        'resources',
        'options'
    ] + Message.__slots__

    def __init__(self, resources=None, options=None, **kwargs):
        """
        Create message with resource request
        :param str resources: resource list
        """
        self.resources = resources
        self.options = options
        super(MessageResourceList, self).__init__(**kwargs)


def init_messages():
    """Add supported messages to register messages list"""
    if registered_message_types:
        return
    for message_class in \
            (
            # Basic messages
            MessageHello,
            MessageRandVal,
            MessageDisconnect,
            MessageChallengeSolution,

            # P2P messages
            MessagePing,
            MessagePong,
            MessageGetPeers,
            MessageGetTasks,
            MessagePeers,
            MessageTasks,
            MessageRemoveTask,
            MessageFindNode,
            MessageGetResourcePeers,
            MessageResourcePeers,
            MessageWantToStartTaskSession,
            MessageSetTaskSession,
            MessageNatHole,
            MessageNatTraverseFailure,
            MessageInformAboutNatTraverseFailure,
            # Ranking messages
            MessageDegree,
            MessageGossip,
            MessageStopGossip,
            MessageLocRank,

            # Task messages
            MessageCannotAssignTask,
            MessageCannotComputeTask,
            MessageTaskToCompute,
            MessageWantToComputeTask,
            MessageReportComputedTask,
            MessageTaskResultHash,
            MessageTaskFailure,
            MessageGetTaskResult,
            MessageStartSessionResponse,
            MessageMiddleman,
            MessageJoinMiddlemanConn,
            MessageBeingMiddlemanAccepted,
            MessageMiddlemanAccepted,
            MessageMiddlemanReady,
            MessageNatPunch,
            MessageWaitForNatTraverse,
            MessageNatPunchFailure,
            MessageWaitingForResults,
            MessageSubtaskResultAccepted,
            MessageSubtaskResultRejected,
            MessageDeltaParts,

            # Resource messages
            MessageGetResource,
            MessagePushResource,
            MessageHasResource,
            MessageWantsResource,
            MessagePullResource,
            MessagePullAnswer,
            MessageResourceList,

            MessageSubtaskPayment,
            MessageSubtaskPaymentRequest,
            ):
        if message_class.TYPE in registered_message_types:
            raise RuntimeError(
                "Duplicated message {}.TYPE: {}"
                .format(message_class.__name__, message_class.TYPE)
            )
        registered_message_types[message_class.TYPE] = message_class
