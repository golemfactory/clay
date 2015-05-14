
import sys
sys.path.append('core')

import abc
from golem.core.simpleserializer import SimpleSerializer
from golem.core.databuffer import DataBuffer
import logging

logger = logging.getLogger(__name__)

class Message:

    registeredMessageTypes = {}

    def __init__( self, type ):
        if type not in Message.registeredMessageTypes:
            Message.registeredMessageTypes[ type ] = self.__class__

        self.type = type
        self.serializer = DataBuffer()

    def getType( self ):
        return self.type

    def serializeWithHeader( self ):
        self.serializeToBuffer(self.serializer)
        return self.serializer.readAll()

    def serialize( self ):
        return SimpleSerializer.dumps( [ self.type, self.dictRepr() ] )

    def serializeToBuffer( self, db ):
        assert isinstance( db, DataBuffer )
        db.appendLenPrefixedString( self.serialize() )

    @classmethod
    def deserialize( cls, db ):
        assert isinstance( db, DataBuffer )
        messages = []
        msg = db.readLenPrefixedString()

        while msg:
            m = cls.deserializeMessage( msg )
            
            if m is None:
                logger.error( "Failed to deserialize message {}".format( msg ) )
                assert False
 
            messages.append( m )
            msg = db.readLenPrefixedString()

        return messages
  
    @classmethod
    def deserializeMessage( cls, msg ):
        msgRepr = SimpleSerializer.loads( msg )

        msgType = msgRepr[ 0 ]
        dRepr   = msgRepr[ 1 ]

        if msgType in cls.registeredMessageTypes:
            return cls.registeredMessageTypes[ msgType ]( dictRepr = dRepr )

        return None

    @abc.abstractmethod
    def dictRepr(self):
        """
        Returns dictionary/list representation of 
        any subclassed message
        """
        return

    def __str__( self ):
        return "{}".format( self.__class__ )

    def __repr__( self ):
        return "{}".format( self.__class__ )



class MessageHello(Message):

    Type = 0

    PROTO_ID_STR    = u"protoId"
    CLI_VER_STR     = u"clientVer"
    PORT_STR        = u"port"
    CLIENT_UID_STR  = u"clientUID"
    CLIENT_KEY_ID_STR = u"clientKeyId"

    def __init__( self, port = 0, clientUID = None, clientKeyId = None, protoId = 0, cliVer = 0,  dictRepr = None ):
        Message.__init__( self, MessageHello.Type )
        
        self.protoId    = protoId
        self.clientVer  = cliVer
        self.port       = port
        self.clientUID  = clientUID
        self.clientKeyId = clientKeyId

        if dictRepr:
            self.protoId    = dictRepr[ MessageHello.PROTO_ID_STR ]
            self.clientVer  = dictRepr[ MessageHello.CLI_VER_STR ]
            self.port       = dictRepr[ MessageHello.PORT_STR ]
            self.clientUID  = dictRepr[ MessageHello.CLIENT_UID_STR ]
            self.clientKeyId = dictRepr[ MessageHello.CLIENT_KEY_ID_STR ]

    def dictRepr(self):
        return {    MessageHello.PROTO_ID_STR : self.protoId,
                    MessageHello.CLI_VER_STR : self.clientVer,
                    MessageHello.PORT_STR : self.port,
                    MessageHello.CLIENT_UID_STR : self.clientUID,
                    MessageHello.CLIENT_KEY_ID_STR: self.clientKeyId
                    }

class MessagePing(Message):

    Type = 1

    PING_STR = u"PING"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessagePing.Type)
        
        if dictRepr:
            assert dictRepr[ 0 ] == MessagePing.PING_STR

    def dictRepr(self):
        return [ MessagePing.PING_STR ]

class MessagePong(Message):

    Type = 2

    PONG_STR = u"PONG"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessagePong.Type)
        
        if dictRepr:
            assert dictRepr[ 0 ] == MessagePong.PONG_STR

    def dictRepr(self):
        return [ MessagePong.PONG_STR ]

class MessageDisconnect(Message):

    Type = 3

    DISCONNECT_REASON_STR = u"DISCONNECT_REASON"

    def __init__( self, reason = -1, dictRepr = None ):
        Message.__init__( self, MessageDisconnect.Type )

        self.reason = reason

        if dictRepr:
            self.reason = dictRepr[ MessageDisconnect.DISCONNECT_REASON_STR ]

    def dictRepr( self ):
        return { MessageDisconnect.DISCONNECT_REASON_STR : self.reason }

class MessageGetPeers( Message ):

    Type = 4

    GET_PEERS_STR = u"GET_PEERS"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessageGetPeers.Type)
        
        if dictRepr:
            assert dictRepr[ 0 ] == MessageGetPeers.GET_PEERS_STR

    def dictRepr(self):
        return [ MessageGetPeers.GET_PEERS_STR ]

class MessagePeers( Message ):

    Type = 5

    PEERS_STR = u"PEERS"

    def __init__( self, peersArray = None, dictRepr = None ):
        Message.__init__(self, MessagePeers.Type)

        if peersArray is None:
            peersArray = []

        self.peersArray = peersArray

        if dictRepr:
            self.peersArray = dictRepr[ MessagePeers.PEERS_STR ]

    def dictRepr(self):
        return { MessagePeers.PEERS_STR : self.peersArray }

class MessageGetTasks( Message ):

    Type = 6

    GET_TASTKS_STR = u"GET_TASKS"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessageGetTasks.Type)

        if dictRepr:
            assert dictRepr[ 0 ] == MessageGetTasks.GET_TASTKS_STR

    def dictRepr(self):
        return [ MessageGetTasks.GET_TASTKS_STR ]

class MessageTasks( Message ):

    Type = 7

    TASKS_STR = u"TASKS"

    def __init__( self, tasksArray = None, dictRepr = None ):
        Message.__init__(self, MessageTasks.Type)

        if tasksArray is None:
            tasksArray = []

        self.tasksArray = tasksArray

        if dictRepr:
            self.tasksArray = dictRepr[ MessageTasks.TASKS_STR ]

    def dictRepr(self):
        return { MessageTasks.TASKS_STR : self.tasksArray }

class MessageRemoveTask( Message ):

    Type = 8

    REMOVE_TASK_STR = u"REMOVE_TASK"

    def __init__( self, taskId = None, dictRepr = None ):
        Message.__init__( self, MessageRemoveTask.Type )

        self.taskId = taskId

        if dictRepr:
            self.taskId = dictRepr[ MessageRemoveTask.REMOVE_TASK_STR ]

    def dictRepr( self ):
        return { MessageRemoveTask.REMOVE_TASK_STR : self.taskId }

class MessageGetResourcePeers( Message ):

    Type = 9

    WANT_RESOURCE_PEERS_STR = u"WANT_RESOURCE_PEERS"

    def __init__( self, dictRepr = None ):
        Message.__init__( self, MessageGetResourcePeers.Type )

        if dictRepr:
            assert dictRepr[ 0 ] == MessageGetResourcePeers.WANT_RESOURCE_PEERS_STR

    def dictRepr( self ):
        return [ MessageGetResourcePeers.WANT_RESOURCE_PEERS_STR ]

class MessageResourcePeers( Message ):

    Type = 10

    RESOURCE_PEERS_STR = u"RESOURCE_PEERS"

    def __init__( self, resourcePeers = None, dictRepr = None ):
        Message.__init__( self, MessageResourcePeers.Type )

        if resourcePeers is None:
            resourcePeers = []

        self.resourcePeers = resourcePeers

        if dictRepr:
            self.resourcePeers = dictRepr[ MessageResourcePeers.RESOURCE_PEERS_STR ]

    def dictRepr( self ):
        return { MessageResourcePeers.RESOURCE_PEERS_STR: self.resourcePeers }

class MessageDegree( Message ):
    Type = 11

    DEGREE_STR = u"DEGREE"

    def __init__(self, degree = None, dictRepr = None):
        Message.__init__( self, MessageDegree.Type )

        self.degree = degree

        if dictRepr:
            self.degree = dictRepr[ MessageDegree.DEGREE_STR ]

    def dictRepr( self ):
        return { MessageDegree.DEGREE_STR: self.degree }

class MessageGossip( Message ):
    Type = 12

    GOSSIP_STR = u"GOSSIP"

    def __init__( self, gossip = None, dictRepr = None):
        Message.__init__( self, MessageGossip.Type )

        self.gossip = gossip

        if dictRepr:
            self.gossip = dictRepr[ MessageGossip.GOSSIP_STR ]

    def dictRepr( self ):
        return { MessageGossip.GOSSIP_STR: self.gossip }

class MessageStopGossip( Message ):
    Type = 13

    STOP_GOSSIP_STR = u"STOP_GOSSIP"

    def __init__( self, dictRepr = None ):
        Message.__init__( self, MessageStopGossip.Type )

        if dictRepr:
            assert dictRepr[ 0 ] == MessageStopGossip.STOP_GOSSIP_STR

    def dictRepr( self ):
        return [ MessageStopGossip.STOP_GOSSIP_STR ]

class MessageLocRank( Message ):
    Type = 14

    NODE_ID_STR = u"NODE_ID"
    LOC_RANK_STR = u"LOC_RANK"

    def __init__( self, nodeId = '', locRank = '', dictRepr = None ):
        Message.__init__( self, MessageLocRank.Type )

        self.nodeId = nodeId
        self.locRank = locRank

        if dictRepr:
            self.nodeId = dictRepr[ MessageLocRank.NODE_ID_STR ]
            self.locRank = dictRepr[ MessageLocRank.LOC_RANK_STR ]

    def dictRepr( self ):
        return { MessageLocRank.NODE_ID_STR: self.nodeId,
                 MessageLocRank.LOC_RANK_STR: self.locRank }

class MessageFindNode( Message ):

    Type = 15

    NODE_KEY_ID_STR = u"NODE_KEY_ID"

    def __init__( self, nodeKeyId = '', dictRepr = None ):
        Message.__init__( self, MessageFindNode.Type )

        self.nodeKeyId = nodeKeyId

        if dictRepr:
            self.nodeKeyId = dictRepr[ MessageFindNode.NODE_KEY_ID_STR ]

    def dictRepr( self ):
        return { MessageFindNode.NODE_KEY_ID_STR: self.nodeKeyId }



TASK_MSG_BASE = 2000

class MessageWantToComputeTask( Message ):

    Type = TASK_MSG_BASE + 1

    CLIENT_ID_STR   = u"CLIENT_ID"
    TASK_ID_STR     = u"TASK_ID"
    PERF_INDEX_STR  = u"PERF_INDEX"
    MAX_RES_STR     = u"MAX_RES"
    MAX_MEM_STR     = u"MAX_MEM"
    NUM_CORES_STR   = u"NUM_CORES"

    def __init__( self, clientId = 0, taskId = 0, perfIndex = 0, maxResourceSize = 0, maxMemorySize = 0, numCores = 0, dictRepr = None ):
        Message.__init__(self, MessageWantToComputeTask.Type)

        self.clientId           = clientId
        self.taskId             = taskId
        self.perfIndex          = perfIndex
        self.maxResourceSize    = maxResourceSize
        self.maxMemorySize      = maxMemorySize
        self.numCores           = numCores

        if dictRepr:
            self.clientId           = dictRepr[ MessageWantToComputeTask.CLIENT_ID_STR ]
            self.taskId             = dictRepr[ MessageWantToComputeTask.TASK_ID_STR ]
            self.perfIndex          = dictRepr[ MessageWantToComputeTask.PERF_INDEX_STR ]
            self.maxResourceSize    = dictRepr[ MessageWantToComputeTask.MAX_RES_STR ]
            self.maxMemorySize      = dictRepr[ MessageWantToComputeTask.MAX_MEM_STR ]
            self.numCores           = dictRepr[ MessageWantToComputeTask.NUM_CORES_STR ]

    def dictRepr(self):
        return {    MessageWantToComputeTask.CLIENT_ID_STR : self.clientId,
                    MessageWantToComputeTask.TASK_ID_STR : self.taskId,
                    MessageWantToComputeTask.PERF_INDEX_STR: self.perfIndex,
                    MessageWantToComputeTask.MAX_RES_STR: self.maxResourceSize,
                    MessageWantToComputeTask.MAX_MEM_STR: self.maxMemorySize,
                    MessageWantToComputeTask.NUM_CORES_STR: self.numCores }

class MessageTaskToCompute( Message ):

    Type = TASK_MSG_BASE + 2

    COMPUTE_TASK_DEF_STR = u"COMPUTE_TASK_DEF"

    def __init__( self, ctd = None, dictRepr = None ):
        Message.__init__( self, MessageTaskToCompute.Type )

        self.ctd = ctd

        if dictRepr:
            self.ctd  = dictRepr[ MessageTaskToCompute.COMPUTE_TASK_DEF_STR ]

    def dictRepr( self ):
        return { MessageTaskToCompute.COMPUTE_TASK_DEF_STR : self.ctd }

class MessageCannotAssignTask( Message ):
    
    Type = TASK_MSG_BASE + 3

    REASON_STR      = u"REASON"
    TASK_ID_STR     = u"TASK_ID"

    def __init__( self, taskId = 0, reason = "", dictRepr = None ):
        Message.__init__(self, MessageCannotAssignTask.Type)

        self.taskId = taskId
        self.reason = reason

        if dictRepr:
            self.taskId      = dictRepr[ MessageCannotAssignTask.TASK_ID_STR ]
            self.reason     = dictRepr[ MessageCannotAssignTask.REASON_STR ]

    def dictRepr(self):
        return {    MessageCannotAssignTask.TASK_ID_STR : self.taskId,
                    MessageCannotAssignTask.REASON_STR: self.reason }

class MessageReportComputedTask( Message ):

    Type = TASK_MSG_BASE + 4

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    RESULT_TYPE_STR = u"RESULT_TYPE"
    NODE_ID_STR = u"NODE_ID"
    ADDR_STR = u"ADDR"
    PORT_STR = u"PORT"
    EXTRA_DATA_STR = u"EXTRA_DATA"
    ETH_ACCOUNT_STR = u"ETH_ACCOUNT"

    def __init__( self, subtaskId = 0, resultType = None, nodeId = '', address = '', port = '', ethAccount = '', extraData = None, dictRepr = None ):
        Message.__init__(self, MessageReportComputedTask.Type)

        self.subtaskId  = subtaskId
        self.resultType = resultType
        self.extraData = extraData
        self.nodeId = nodeId
        self.address = address
        self.port = port
        self.ethAccount = ethAccount

        if dictRepr:
            self.subtaskId  = dictRepr[ MessageReportComputedTask.SUB_TASK_ID_STR ]
            self.resultType = dictRepr[ MessageReportComputedTask.RESULT_TYPE_STR ]
            self.nodeId = dictRepr[ MessageReportComputedTask.NODE_ID_STR ]
            self.address = dictRepr[ MessageReportComputedTask.ADDR_STR ]
            self.port = dictRepr[ MessageReportComputedTask.PORT_STR ]
            self.ethAccount = dictRepr[ MessageReportComputedTask.ETH_ACCOUNT_STR ]
            self.extraData = dictRepr[ MessageReportComputedTask.EXTRA_DATA_STR ]

    def dictRepr(self):
        return {    MessageReportComputedTask.SUB_TASK_ID_STR : self.subtaskId,
                    MessageReportComputedTask.RESULT_TYPE_STR: self.resultType,
                    MessageReportComputedTask.NODE_ID_STR: self.nodeId,
                    MessageReportComputedTask.ADDR_STR: self.address,
                    MessageReportComputedTask.PORT_STR: self.port,
                    MessageReportComputedTask.ETH_ACCOUNT_STR: self.ethAccount,
                    MessageReportComputedTask.EXTRA_DATA_STR: self.extraData }

class MessageGetTaskResult( Message ):

    Type = TASK_MSG_BASE + 5

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    DELAY_STR       = u"DELAY"

    def __init__( self, subtaskId = 0, delay = 0.0, dictRepr = None ):
        Message.__init__(self, MessageGetTaskResult.Type)

        self.subtaskId  = subtaskId
        self.delay      = delay

        if dictRepr:
            self.subtaskId  = dictRepr[ MessageGetTaskResult.SUB_TASK_ID_STR ]
            self.delay      = dictRepr[ MessageGetTaskResult.DELAY_STR ]

    def dictRepr(self):
        return {    MessageGetTaskResult.SUB_TASK_ID_STR : self.subtaskId,
                    MessageGetTaskResult.DELAY_STR: self.delay  }

class MessageTaskResult( Message ):

    Type = TASK_MSG_BASE + 6

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    RESULT_STR      = u"RESULT"

    def __init__( self, subtaskId = 0, result = None, dictRepr = None ):
        Message.__init__(self, MessageTaskResult.Type)

        self.subtaskId  = subtaskId
        self.result     = result

        if dictRepr:
            self.subtaskId  = dictRepr[ MessageTaskResult.SUB_TASK_ID_STR ]
            self.result     = dictRepr[ MessageTaskResult.RESULT_STR ]

    def dictRepr(self):
        return {    MessageTaskResult.SUB_TASK_ID_STR   : self.subtaskId,
                    MessageTaskResult.RESULT_STR        : self.result }

class MessageGetResource( Message ):

    Type = TASK_MSG_BASE + 8

    TASK_ID_STR         = u"SUB_TASK_ID"
    RESOURCE_HEADER_STR = u"RESOURCE_HEADER"

    def __init__( self, taskId = "", resourceHeader = None , dictRepr = None ):
        Message.__init__(self, MessageGetResource.Type)

        self.taskId         = taskId
        self.resourceHeader = resourceHeader

        if dictRepr:
            self.taskId         = dictRepr[ MessageGetResource.TASK_ID_STR ]
            self.resourceHeader = dictRepr[ MessageGetResource.RESOURCE_HEADER_STR ]

    def dictRepr(self):
        return {    MessageGetResource.TASK_ID_STR : self.taskId,
                    MessageGetResource.RESOURCE_HEADER_STR: self.resourceHeader
               }

class MessageResource( Message ):

    Type = TASK_MSG_BASE + 9

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    RESOURCE_STR    = u"RESOURCE"

    def __init__( self, subtaskId = 0, resource = None , dictRepr = None ):
        Message.__init__(self, MessageResource.Type)

        self.subtaskId      = subtaskId
        self.resource       = resource

        if dictRepr:
            self.subtaskId      = dictRepr[ MessageResource.SUB_TASK_ID_STR ]
            self.resource       = dictRepr[ MessageResource.RESOURCE_STR ]

    def dictRepr(self):
        return {    MessageResource.SUB_TASK_ID_STR : self.subtaskId,
                    MessageResource.RESOURCE_STR: self.resource
               }

class MessageSubtaskResultAccepted( Message ):
    Type = TASK_MSG_BASE + 10

    SUB_TASK_ID_STR = u"SUB_TASK_ID"
    NODE_ID_STR     = u"NODE_ID"
    REWARD_STR      = u"REWARD"

    def __init__( self, subtaskId = 0, reward = 0, dictRepr = None ):
        Message.__init__( self, MessageSubtaskResultAccepted.Type )

        self.subtaskId  = subtaskId
        self.reward     = reward

        if dictRepr:
            self.subtaskId  = dictRepr[ MessageSubtaskResultAccepted.SUB_TASK_ID_STR ]
            self.reward     = dictRepr[ MessageSubtaskResultAccepted.REWARD_STR ]

    def dictRepr( self ):
        return {
            MessageSubtaskResultAccepted.SUB_TASK_ID_STR: self.subtaskId,
            MessageSubtaskResultAccepted.REWARD_STR: self.reward
        }

class MessageSubtaskResultRejected( Message ):
    Type = TASK_MSG_BASE + 11

    SUB_TASK_ID_STR = u"SUB_TASK_ID"

    def __init__( self, subtaskId = 0, dictRepr = None ):
        Message.__init__( self, MessageSubtaskResultRejected.Type )

        self.subtaskId = subtaskId

        if dictRepr:
            self.subtaskId = dictRepr[ MessageSubtaskResultRejected.SUB_TASK_ID_STR ]


    def dictRepr( self ):
        return {
            MessageSubtaskResultRejected.SUB_TASK_ID_STR: self.subtaskId
        }

class MessageDeltaParts( Message ):
    Type = TASK_MSG_BASE + 12

    TASK_ID_STR = u"TASK_ID"
    DELTA_HEADER_STR = u"DELTA_HEADER"
    PARTS_STR = u"PARTS"
    CLIENT_ID_STR = u"CLIENT_ID"
    ADDR_STR = u"ADDR"
    PORT_STR = u"PORT"

    def __init__( self, taskId = 0, deltaHeader = None, parts = None, clientId = '', addr  = '', port = '', dictRepr = None ):
        Message.__init__( self, MessageDeltaParts.Type )

        self.taskId = taskId
        self.deltaHeader = deltaHeader
        self.parts = parts
        self.clientId = clientId
        self.addr = addr
        self.port = port

        if dictRepr:
            self.taskId = dictRepr[ MessageDeltaParts.TASK_ID_STR ]
            self.deltaHeader = dictRepr[ MessageDeltaParts.DELTA_HEADER_STR ]
            self.parts = dictRepr[ MessageDeltaParts.PARTS_STR ]
            self.clientId = dictRepr[ MessageDeltaParts.CLIENT_ID_STR ]
            self.addr = dictRepr[ MessageDeltaParts.ADDR_STR ]
            self.port = dictRepr[ MessageDeltaParts.PORT_STR ]

    def dictRepr( self ):
        return {
            MessageDeltaParts.TASK_ID_STR: self.taskId,
            MessageDeltaParts.DELTA_HEADER_STR: self.deltaHeader,
            MessageDeltaParts.PARTS_STR: self.parts,
            MessageDeltaParts.CLIENT_ID_STR: self.clientId,
            MessageDeltaParts.ADDR_STR: self.addr,
            MessageDeltaParts.PORT_STR: self.port
        }

class MessageResourceFormat( Message ):
    Type = TASK_MSG_BASE + 13

    USE_DISTRIBUTED_RESOURCE_STR = u"USE_DISTRIBUTED_RESOURCE"

    def __init__( self, useDistributedResource = 0, dictRepr = None ):
        Message.__init__( self, MessageResourceFormat.Type )

        self.useDistributedResource = useDistributedResource

        if dictRepr:
            self.useDistributedResource = dictRepr[ MessageResourceFormat.USE_DISTRIBUTED_RESOURCE_STR ]

    def dictRepr( self ):
        return {
            MessageResourceFormat.USE_DISTRIBUTED_RESOURCE_STR: self.useDistributedResource
        }

class MessageAcceptResourceFormat( Message ):
    Type = TASK_MSG_BASE + 14

    ACCEPT_RESOURCE_FORMAT_STR = u"ACCEPT_RESOURCE_FORMAT"

    def __init__( self, dictRepr = None ):
        Message.__init__( self, MessageAcceptResourceFormat.Type )

        if dictRepr:
            assert dictRepr[0] == MessageAcceptResourceFormat.ACCEPT_RESOURCE_FORMAT_STR


    def dictRepr( self ):
        return [ MessageAcceptResourceFormat.ACCEPT_RESOURCE_FORMAT_STR ]

class MessageTaskFailure( Message):
    Type = TASK_MSG_BASE + 15

    SUBTASK_ID_STR = u"SUBTASK_ID"
    ERR_STR = u"ERR"

    def __init__(self, subtaskId = "", err = "", dictRepr = None ):
        Message.__init__( self, MessageTaskFailure.Type )

        self.subtaskId = subtaskId
        self.err = err

        if dictRepr:
            self.subtaskId = dictRepr[ MessageTaskFailure.SUBTASK_ID_STR ]
            self.err = dictRepr[ MessageTaskFailure.ERR_STR ]

    def dictRepr( self ):
        return {
            MessageTaskFailure.SUBTASK_ID_STR: self.subtaskId,
            MessageTaskFailure.ERR_STR: self.err
        }

RESOURCE_MSG_BASE = 3000

class MessagePushResource( Message ):

    Type = RESOURCE_MSG_BASE + 1

    RESOURCE_STR = u"resource"
    COPIES_STR = u"copies"

    def __init__( self, resource = None, copies = 0, dictRepr = None ):
        Message.__init__( self, MessagePushResource.Type )
        self.resource = resource
        self.copies = copies

        if dictRepr:
            self.resource = dictRepr[ MessagePushResource.RESOURCE_STR ]
            self.copies = dictRepr[ MessagePushResource.COPIES_STR ]

    def dictRepr( self ):
        return {    MessagePushResource.RESOURCE_STR: self.resource,
                    MessagePushResource.COPIES_STR: self.copies
        }
class MessageHasResource( Message ):

    Type = RESOURCE_MSG_BASE + 2

    RESOURCE_STR = u"resource"

    def __init__( self, resource = None, dictRepr = None ):
        Message.__init__( self, MessageHasResource.Type )
        self.resource = resource

        if dictRepr:
            self.resource = dictRepr[ MessageHasResource.RESOURCE_STR ]

    def dictRepr( self ):
        return { MessageHasResource.RESOURCE_STR: self.resource }

class MessageWantResource( Message ):

    Type = RESOURCE_MSG_BASE + 3

    RESOURCE_STR = u"resource"

    def __init__( self, resource = None, dictRepr = None ):
        Message.__init__( self, MessageWantResource.Type )
        self.resource = resource

        if dictRepr:
            self.resource = dictRepr[ MessageWantResource.RESOURCE_STR ]

    def dictRepr( self ):
        return { MessageWantResource.RESOURCE_STR : self.resource }


class MessagePullResource( Message ):

    Type = RESOURCE_MSG_BASE + 4

    RESOURCE_STR = u"resource"

    def __init__( self, resource = None, dictRepr = None ):
        Message.__init__( self, MessagePullResource.Type )
        self.resource = resource

        if dictRepr:
            self.resource = dictRepr[ MessagePullResource.RESOURCE_STR ]

    def dictRepr( self ):
        return { MessagePullResource.RESOURCE_STR : self.resource }

class MessagePullAnswer( Message ):

    Type = RESOURCE_MSG_BASE + 5

    RESOURCE_STR = u"resource"
    HAS_RESOURCE_STR = u"hasResource"

    def __init__( self, resource = None, hasResource = False, dictRepr = None ):
        Message.__init__( self, MessagePullAnswer.Type )
        self.resource = resource
        self.hasReource = hasResource

        if dictRepr:
            self.resource = dictRepr[ MessagePullAnswer.RESOURCE_STR ]
            self.hasResource = dictRepr[ MessagePullAnswer.HAS_RESOURCE_STR ]

    def dictRepr( self ):
        return { MessagePullAnswer.RESOURCE_STR: self.resource,
                 MessagePullAnswer.HAS_RESOURCE_STR: self.hasReource }

class MessageSendResource( Message ):

    Type = RESOURCE_MSG_BASE + 6

    RESOURCE_STR = u"resource"

    def __init__( self, resource = None, dictRepr = None ):
        Message.__init__( self, MessageSendResource.Type )
        self.resource = resource

        if dictRepr:
            self.resource = dictRepr[ MessageSendResource.RESOURCE_STR ]

    def dictRepr( self ):
        return { MessageSendResource.RESOURCE_STR: self.resource }

MANAGER_MSG_BASE = 1000

class MessagePeerStatus( Message ):

    Type = MANAGER_MSG_BASE + 1

    ID_STR      = u"ID"
    DATA_STR    = u"DATA"

    def __init__( self, id = "", data = "", dictRepr = None ):
        Message.__init__(self, MessagePeerStatus.Type)

        self.id = id
        self.data = data

        if dictRepr:
            self.id = dictRepr[ self.ID_STR ]
            self.data = dictRepr[ self.DATA_STR ]

    def dictRepr(self):
        return { self.ID_STR : self.id, self.DATA_STR : self.data } 

    def __str__( self ):
        return "{} {}".format( self.id, self.data )

class MessageNewTask( Message ):
    Type = MANAGER_MSG_BASE + 2

    DATA_STR    = u"DATA"

    def __init__( self, data = "", dictRepr = None ):
        Message.__init__(self, MessageNewTask.Type)

        self.data = data

        if dictRepr:
            self.data = dictRepr[ self.DATA_STR ]

    def dictRepr(self):
        return { self.DATA_STR : self.data } 

    def __str__( self ):
        return "{}".format( self.data )

class MessageKillNode( Message ):
    Type = MANAGER_MSG_BASE + 3

    KILL_STR    = u"KILL"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessageKillNode.Type)

        if dictRepr:
            assert dictRepr[ 0 ] == MessageKillNode.KILL_STR

    def dictRepr(self):
        return [ MessageKillNode.KILL_STR ]

class MessageKillAllNodes( Message ):
    Type = MANAGER_MSG_BASE + 4

    KILLALL_STR = u"KILLALL"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessageKillAllNodes.Type)

        if dictRepr:
            assert dictRepr[ 0 ] == MessageKillAllNodes.KILLALL_STR

    def dictRepr(self):
        return [ MessageKillAllNodes.KILLALL_STR ]


class MessageNewNodes( Message ):
    Type = MANAGER_MSG_BASE + 5

    NUM_STR = u"NUM"

    def __init__( self, num = 0, dictRepr = None ):
        Message.__init__( self, MessageNewNodes.Type )

        self.num = num

        if dictRepr:
            self.num = dictRepr[ self.NUM_STR ]

    def dictRepr( self ):
        return { MessageNewNodes.NUM_STR : self.num }

def initMessages():
    MessageHello()
    MessagePing()
    MessagePong()
    MessageDisconnect()
    MessageCannotAssignTask()
    MessageGetPeers()
    MessageGetTasks()
    MessagePeers()
    MessageTasks()
    MessageRemoveTask()
    MessageGetResourcePeers()
    MessageResourcePeers()
    MessageDegree()
    MessageGossip()
    MessageStopGossip()
    MessageLocRank()
    MessageFindNode()

    MessageTaskToCompute()
    MessageWantToComputeTask()
    MessagePeerStatus()
    MessageNewTask()
    MessageKillNode()
    MessageKillAllNodes()
    MessageGetResource()
    MessageResource()
    MessageReportComputedTask()
    MessageTaskResult()
    MessageTaskFailure()
    MessageGetTaskResult()
    MessageNewNodes()
    MessageSubtaskResultAccepted()
    MessageSubtaskResultRejected()
    MessageDeltaParts()
    MessageResourceFormat()
    MessageAcceptResourceFormat()

    MessagePushResource()
    MessageHasResource()
    MessageWantResource()
    MessagePullResource()
    MessagePullAnswer()
    MessageSendResource()

def initManagerMessages():
    MessagePeerStatus()
    MessageKillNode()
    MessageKillAllNodes()
    MessageNewTask()
    MessageNewNodes()



if __name__ == "__main__":

    hem = MessageHello( 1, 2 )
    pim = MessagePing()
    pom = MessagePong()
    dcm = MessageDisconnect(3)

    print hem
    print pim
    print pom
    print dcm

    db = DataBuffer()
    db.appendLenPrefixedString( hem.serialize() )
    db.appendLenPrefixedString( pim.serialize() )
    db.appendLenPrefixedString( pom.serialize() )
    db.appendLenPrefixedString( dcm.serialize() )

    print db.dataSize()
    streamedData = db.readAll()
    print len( streamedData )

    db.appendString( streamedData )

    messages = Message.deserialize( db )

    for msg in messages:
        print msg
