from twisted.internet.protocol import Protocol 
from message import Message, MessageHello, MessagePing, MessagePong
from databuffer import DataBuffer

class ConnectionState(Protocol):

    def __init__(self, server):
        self.server = server
        self.peer = None
        self.db = DataBuffer()
        self.opened = False

    def sendMessage(self, msg):
        if not self.opened:
            print "sendMessage failed - connection closed."
            return False
        db = DataBuffer()
        db.appendLenPrefixedString( msg )
        self.transport.getHandle()
        self.transport.write( db.readAll() )
        return True

    def connectionMade(self):
        assert False # Implement in derived class

    def dataReceived(self, data):
        assert False # Implement in derived class

    def connectionLost(self, reason):
        assert False # Implement in derived class

    def close(self):
        self.transport.loseConnection()

    def isOpen(self):
        return self.opened
