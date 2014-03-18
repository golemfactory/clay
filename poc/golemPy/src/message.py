import abc
import databuffer
import json
import time

PingMessage = "\0x02"
PongMessage = "\0x03"

class Message:

    def __init__( self, type ):
        self.type = type
        self.serializer = databuffer.DataBuffer()

    def getType( self ):
        return self.type

    def serialize( self ):
        strJSONRepr = json.dumps( [ self.type, self.dictRepr() ] )
        self.seralizer.appendLenPrefixedString( strJSONRepr )

        return self.serializer.readAll()

    @classmethod
    def deserialize( cls, db ):
        assert isinstance( db, databuffer.DataBuffer )
        messages = []
        msg = db.readLenPrefixedString()

        while msg:
            messages.append( msg )
            msg = db.readLenPrefixedString()

        return messages
  
    @classmethod
    def deserializeMessage( cls, msg ):
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


class HelloMessage(Message):

    Type = 0

    def __init__( self, protoId, cliVer ):
        Message.__init__( self, HelloMessage.Type )
        self.protoId    = protoId
        self.clientVer  = cliVer

    def __init__( self, dictRepr ):
        self.protoId    = dictRepr[ "protoId" ]
        self.clientVer  = dictRepr[ "clientVer" ]

    def dictRepr(self):
        
        return super(HelloMessage, self).dictRepr()( sel
    def serializeTyped(self):
        return json.dumps([HelloMessage.Type, "Hello World !!!"])

class PingMessage(Message):

    Type = 1

    def __init__(self):
        Message.__init__(self, PingMessage.Type)

    def serializeTyped(self):
        return json.dumps([PingMessage.Type, "Ping"])

class PongMessage(Message):

    Type = 2

    def __init__(self):
        Message.__init__(self, PongMessage.Type)

    def serializeTyped(self):
        return json.dumps([PongMessage.Type ,"Pong"])