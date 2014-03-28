from message import Message
from connectionstate import ConnectionState

class TaskConnState( ConnectionState ):
    ##########################
    def __init__(self, server):
        ConnectionState.__init__( self, server )
        self.computeSession = None

    ############################
    def setComputeSession( self, computeSesssion ):
        self.computeSession = computeSesssion

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
            self.computeSession.interpret(None)

        if self.computeSession:
            for m in mess:
                self.computeSession.interpret(m)
        else:
            print "Peer for connection is None"
            assert False

    ############################
    def connectionLost(self, reason):
        self.opened = False

        if self.computeSession:
            self.computeSession.dropped()