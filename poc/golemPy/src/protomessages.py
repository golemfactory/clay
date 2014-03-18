from message import Message
from databuffer import DataBuffer

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

    PING_STR = u"PING"

    def __init__( self, dictRepr = None ):
        Message.__init__(self, MessagePing.Type)
        
        if dictRepr:
            assert dictRepr[ 0 ] == MessagePing.PING_STR

    def dictRepr(self):
        return [ MessagePing.PING_STR ]

class MessagePong(Message):

    Type = 2

    PONG_STR = "PONG"

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

    print db.dataSize()
    streamedData = db.readAll();
    print len( streamedData )

    db.appendString( streamedData )

    messages = Message.deserialize( db )

    for msg in messages:
        print msg
