
import sys
sys.path.append('core')

import abc
from golem.core.simpleserializer import SimpleSerializer
from golem.core.databuffer import DataBuffer

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
                print "Failed to deserialize message {}".format( msg )
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

    def __init__( self, port = 0, clientUID = None, protoId = 0, cliVer = 0, dictRepr = None ):
        Message.__init__( self, MessageHello.Type )
        
        self.protoId    = protoId
        self.clientVer  = cliVer
        self.port       = port
        self.clientUID  = clientUID

        if dictRepr:
            self.protoId    = dictRepr[ MessageHello.PROTO_ID_STR ]
            self.clientVer  = dictRepr[ MessageHello.CLI_VER_STR ]
            self.port       = dictRepr[ MessageHello.PORT_STR ]
            self.clientUID  = dictRepr[ MessageHello.CLIENT_UID_STR ]

    def dictRepr(self):
        return {    MessageHello.PROTO_ID_STR : self.protoId,
                    MessageHello.CLI_VER_STR : self.clientVer,
                    MessageHello.PORT_STR : self.port,
                    MessageHello.CLIENT_UID_STR : self.clientUID
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

    def __init__( self, peersArray = [], dictRepr = None ):
        Message.__init__(self, MessagePeers.Type)
        
        self.peersArray = peersArray

        if dictRepr:
            self.peersArray = dictRepr[ MessagePeers.PEERS_STR ]

    def dictRepr(self):
        return { MessagePeers.PEERS_STR : self.peersArray }

class MessageGetTasks( Message ):

    Type = 6

    GET_TASTKS_STR = u"GET_TASKS"

    def __init__( self, peersArray = [], dictRepr = None ):
        Message.__init__(self, MessageGetTasks.Type)

        if dictRepr:
            assert dictRepr[ 0 ] == MessageGetTasks.GET_TASTKS_STR

    def dictRepr(self):
        return [ MessageGetTasks.GET_TASTKS_STR ]

class MessageTasks( Message ):

    Type = 7

    TASKS_STR = u"TASKS"

    def __init__( self, tasksArray = [], dictRepr = None ):
        Message.__init__(self, MessageTasks.Type)
        
        self.tasksArray = tasksArray

        if dictRepr:
            self.tasksArray = dictRepr[ MessageTasks.TASKS_STR ]

    def dictRepr(self):
        return { MessageTasks.TASKS_STR : self.tasksArray }

TASK_MSG_BASE = 2000

class MessageWantToComputeTask( Message ):

    Type = TASK_MSG_BASE + 1

    CLIENT_ID_STR   = u"CLIENT_ID"
    TASK_ID_STR     = u"TASK_ID"
    PERF_INDEX_STR  = u"PERF_INDEX"

    def __init__( self, clientId = 0, taskId = 0, perfIndex = 0, dictRepr = None ):
        Message.__init__(self, MessageWantToComputeTask.Type)

        self.clientId   = clientId
        self.taskId     = taskId
        self.perfIndex  = perfIndex

        if dictRepr:
            self.clientId   = dictRepr[ MessageWantToComputeTask.CLIENT_ID_STR ]
            self.taskId     = dictRepr[ MessageWantToComputeTask.TASK_ID_STR ]
            self.perfIndex  = dictRepr[ MessageWantToComputeTask.PERF_INDEX_STR ]

    def dictRepr(self):
        return {    MessageWantToComputeTask.CLIENT_ID_STR : self.clientId,
                    MessageWantToComputeTask.TASK_ID_STR : self.taskId,
                    MessageWantToComputeTask.PERF_INDEX_STR: self.perfIndex }

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

    def __init__( self, subtaskId = 0, dictRepr = None ):
        Message.__init__(self, MessageReportComputedTask.Type)

        self.subtaskId  = subtaskId

        if dictRepr:
            self.subtaskId  = dictRepr[ MessageReportComputedTask.SUB_TASK_ID_STR ]

    def dictRepr(self):
        return {    MessageReportComputedTask.SUB_TASK_ID_STR : self.subtaskId }

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
    MessageTaskToCompute()
    MessageWantToComputeTask()
    MessagePeerStatus()
    MessageNewTask()
    MessageKillNode()
    MessageGetResource()
    MessageResource()
    MessageReportComputedTask()
    MessageTaskResult()
    MessageGetTaskResult()


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
    streamedData = db.readAll();
    print len( streamedData )

    db.appendString( streamedData )

    messages = Message.deserialize( db )

    for msg in messages:
        print msg
