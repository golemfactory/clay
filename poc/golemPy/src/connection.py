from twisted.internet.protocol import Protocol 
from message import Message, MessageHello, MessagePing, MessagePong
from databuffer import DataBuffer

class GolemConnection(Protocol):

    def __init__(self, server):
        self.server = server
        self.peer = None
        self.db = DataBuffer()

    def setPeerSession(self, peerSession):
        self.peer = peerSession

    def sendMessage(self, msg):
        db = DataBuffer()
        db.appendLenPrefixedString( msg )
        self.transport.getHandle()
        self.transport.write( db.readAll() )

    def connectionMade(self):
        self.server.newConnection(self)

    def dataReceived(self, data):
        self.db.appendString(data)
        mess = Message.deserialize(self.db)
        if mess is None:
            print "Deserialization message failed"
            self.peer.interpret(None)

        if self.peer:
            for m in mess:
                self.peer.interpret(m)
        else:
            print "Peer for connection is None"
            assert False

    def close(self):
        self.transport.loseConnection()

    def isOpen(self):
        return self.transport.isOpen()