import abc

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
            print msg
            print "sendMessage failed - connection closed."
            return False

        serMsg = msg.serialize()

        db = DataBuffer()
        db.appendLenPrefixedString( serMsg )
        self.transport.getHandle()
        self.transport.write( db.readAll() )

        return True

    @abc.abstractmethod
    def connectionMade(self):
        """Called when new connection is successfully opened"""
        return

    @abc.abstractmethod
    def dataReceived(self, data):
        """Called when additional chunk of data is received from another peer"""
        return

    @abc.abstractmethod
    def connectionLost(self, reason):
        """Called when connection is lost (for whatever reason)"""
        return

    def close(self):
        self.transport.loseConnection()

    def isOpen(self):
        return self.opened
