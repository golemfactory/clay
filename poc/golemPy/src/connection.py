from twisted.internet.protocol import Protocol 
from message import MessageHello, MessagePing, MessagePong
from databuffer import DataBuffer
from message import Message
from p2pserver import P2PServerInterface
from peer import PeerSessionInterface

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
        self.transport.write( db.readAll() )

    def connectionMade(self):
        self.server.newConnection(self)

    def dataReceived(self, data):
        self.db.appendString(data)
        mess = Message.deserialize(self.db)
        if mess is None:
            print "Deserialization message failed"
            return

        if self.peer:
            for m in mess:
                self.peer.interpret(self, m)

