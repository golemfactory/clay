from message import Message
from connectionstate import ConnectionState

class TaskConnState( ConnectionState ):
    ##########################
    def __init__(self, server):
        ConnectionState.__init__( self, server )
        self.taskSession = None

    ############################
    def setTaskSession( self, taskSession ):
        self.taskSession = taskSession

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
            self.taskSesssion.interpret(None)

        if self.taskSesssion:
            for m in mess:
                self.taskSession.interpret(m)
        else:
            print "Task session for connection is None"
            assert False

    ############################
    def connectionLost(self, reason):
        self.opened = False

        if self.taskSession:
            self.taskSession.dropped()
