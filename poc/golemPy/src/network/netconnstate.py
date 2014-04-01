from message import Message
from connectionstate import ConnectionState

class NetConnState( ConnectionState ):
    ############################
    def __init__( self, server = None ):
        ConnectionState.__init__( self )
        self.peer = None
        self.server = server
    
    ############################
    def setSession( self, session ):
        self.peer = session

    ############################
    def connectionMade(self):
        self.opened = True

        if self.server:
            from peer import PeerSession
            pp = self.transport.getPeer()
            self.peer = PeerSession( self )
            self.server.newConnection( self.peer )

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
