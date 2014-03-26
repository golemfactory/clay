import sys
sys.path.append('core')

import abc
from simpleserializer import SimpleSerializer
from databuffer import DataBuffer

class Message:

    def __init__( self, type ):
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

        if msgType == MessageHello.Type:
            return MessageHello( dictRepr = dRepr )
        elif msgType == MessagePing.Type:
            return MessagePing( dictRepr = dRepr )
        elif msgType == MessagePong.Type:
            return MessagePong( dictRepr = dRepr )
        elif msgType == MessageDisconnect.Type:
            return MessageDisconnect( dictRepr = dRepr )
        elif msgType == MessageGetPeers.Type:
            return MessageGetPeers( dictRepr = dRepr )
        elif msgType == MessagePeers.Type:
            return MessagePeers( dictRepr = dRepr )
        elif msgType == MessageGetTasks.Type:
            return MessageGetTasks( dictRepr = dRepr )
        elif msgType == MessageTasks.Type:
            return MessageTasks( dictRepr = dRepr )
        elif msgType == MessageWantToComputeTask.Type:
            return MessageWantToComputeTask( dictRepr = dRepr )
        elif msgType == MessageTaskToCompute.Type:
            return MessageTaskToCompute( dictRepr = dRepr )

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

class MessageWantToComputeTask( Message ):

    Type = 8

    TASK_ID_STR     = u"TASK_ID"
    PERF_INDEX_STR  = u"PERF_INDEX"

    def __init__( self, taskId = 0, perfIndex = 0, dictRepr = None ):
        Message.__init__(self, MessageWantToComputeTask.Type)

        self.taskId = taskId
        self.perfIndex = perfIndex

        if dictRepr:
            self.taskId     = dictRepr[ MessageWantToComputeTask.TASK_ID_STR ]
            self.perfIndex  = dictRepr[ MessageWantToComputeTask.PERF_INDEX_STR ]

    def dictRepr(self):
        return {    MessageWantToComputeTask.TASK_ID_STR : self.taskId,
                    MessageWantToComputeTask.PERF_INDEX_STR: self.perfIndex }

class MessageTaskToCompute( Message ):

    Type = 9

    TASK_ID_STR     = u"TASK_ID"
    EXTRA_DATA_STR  = u"EXTRA_DATA"
    SOURCE_CODE_STR = u"SOURCE_CODE"

    def __init__( self, taskId = 0, extraData = {}, sourceCode = "", dictRepr = None ):
        Message.__init__(self, MessageTaskToCompute.Type)

        self.taskId = taskId
        self.extraData = extraData
        self.sourceCode = sourceCode

        if dictRepr:
            self.taskId     = dictRepr[ MessageTaskToCompute.TASK_ID_STR ]
            self.extraData  = dictRepr[ MessageTaskToCompute.EXTRA_DATA_STR ]
            self.sourceCode = dictRepr[ MessageTaskToCompute.SOURCE_CODE_STR ]

    def dictRepr(self):
        return {    MessageTaskToCompute.TASK_ID_STR : self.taskId,
                    MessageTaskToCompute.EXTRA_DATA_STR: self.extraData,
                    MessageTaskToCompute.SOURCE_CODE_STR: self.sourceCode }

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
