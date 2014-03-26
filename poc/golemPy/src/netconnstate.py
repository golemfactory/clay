from message import Message
from connectionstate import ConnectionState

class NetConnState( ConnectionState ):
    ############################
    def __init__( self, server ):
        ConnectionState.__init__( self, server )
        self.peer = None
    
    ############################
    def setPeerSession(self, peerSession):
        self.peer = peerSession

    ############################
    def connectionMade(self):
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
