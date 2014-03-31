import sys
sys.path.append( '/..')

from message import Message
from connectionstate import ConnectionState

class ManagerConnectionState( ConnectionState ):

    ############################
    def __init__( self, manager = None ):
        ConnectionState.__init__( self, none )
        self.manager = manager

    ############################
    def setManager( self, manager ):
        self.manager = manager

    ############################
    def connectionMade( self ):
        self.opened = True
        self.server.newConnection(self)

    ############################
    def dataReceived(self, data):
        assert self.opened

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

    ############################
    def connectionLost(self, reason):
        self.opened = False
        self.peer.dropped()
