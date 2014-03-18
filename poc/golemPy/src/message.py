import abc
import json
from databuffer import DataBuffer

class Message:

    def __init__( self, type ):
        self.type = type
        self.serializer = DataBuffer()

    def getType( self ):
        return self.type

    def serialize( self ):
        strJSONRepr = json.dumps( [ self.type, self.dictRepr() ] )
        print strJSONRepr
        self.serializer.appendLenPrefixedString( strJSONRepr )

        return self.serializer.readAll()

    @classmethod
    def deserialize( cls, db ):
        assert isinstance( db, DataBuffer )
        messages = []
        msg = db.readLenPrefixedString()

        while msg:
            m = cls.deserializeMessage( msg )
            
            if m is None:
                print "Failed to deserialize message {}".format( msg )
                assert false
 
            messages.append( m )
            msg = db.readLenPrefixedString()

        return messages
  
    @classmethod
    def deserializeMessage( cls, msg ):
        print msg, msg.__class__
        msgRepr  = json.loads( msg )

        msgType  = msgRepr[ 0 ]
        dictRepr = msgRepr[ 1 ]

        if messType == HelloMessage.Type:
            return HelloMessage( dictRepr )
        elif messType == PingMessage.Type:
            return PingMessage( dictRepr )
        elif messType == PongMessage.Type:
            return PongMessage( dictRepr )

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

    PROTO_ID_STR = "protoId"
    CLI_VER_STR =  "clientVer"

    def __init__( self, protoId = 0, cliVer = 0, dictRepr = None ):
        Message.__init__( self, MessageHello.Type )
        
        self.protoId    = protoId
        self.clientVer  = cliVer

        if dictRepr:
            self.protoId    = dictRepr[ MessageHello.PROTO_ID_STR ]
            self.clientVer  = dictRepr[ MessageHello.CLI_VER_STR ]

    def dictRepr(self):
        return { MessageHello.PROTO_ID_STR : self.protoId, MessageHello.CLI_VER_STR : self.clientVer }

class MessagePing(Message):

    Type = 1

    PING_STR = "PING"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessagePing.Type)
        
        if dictRepr:
            assert dictRepr[ 0 ] == MessagePing.PING_STR

    def dictRepr(self):
        return [ MessagePing.PING_STR ]

class MessagePong(Message):

    Type = 1

    PONG_STR = "PONG"

    def __init__( self ):
        Message.__init__(self, MessagePong.Type)

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessagePong.Type)
        
        if dictRepr:
            assert dictRepr[ 0 ] == MessagePong.PONG_STR

    def dictRepr(self):
        return [ MessagePong.PONG_STR ]

if __name__ == "__main__":

    hem = MessageHello( 1, 2 )
    pim = MessagePing()
    pom = MessagePong()

    print hem
    print pim
    print pom

    db = DataBuffer()
    db.appendLenPrefixedString( hem.serialize() )
    db.appendLenPrefixedString( pim.serialize() )
    db.appendLenPrefixedString( pom.serialize() )

    print db

    streamedData = db.readAll();

    print streamedData

    db.appendString( streamedData )

    messages = Message.deserialize( db )

    for msg in messages:
        print msg