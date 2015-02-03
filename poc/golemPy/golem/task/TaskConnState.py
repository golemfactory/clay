
from golem.Message import Message
from golem.network.p2p.ConnectionState import ConnectionState
import logging

logger = logging.getLogger(__name__)

class TaskConnState( ConnectionState ):
    ##########################
    def __init__( self, server = None):
        ConnectionState.__init__( self )
        self.taskSession = None
        self.server = server
        self.fileMode = False
        self.dataMode = False

    ############################
    def setSession( self, taskSession ):
        self.taskSession = taskSession

    ############################
    def connectionMade(self):
        self.opened = True

        if self.server:
            from TaskSession import TaskSession
            pp = self.transport.getPeer()
            self.taskSession = TaskSession( self )
            self.server.newConnection( self.taskSession )

    ############################
    def dataReceived(self, data):
        assert self.opened

        if self.fileMode:
            self.fileDataReceived( data )
            return

        if self.dataMode:
            self.resultDataReceived( data )
            return

        self.db.appendString(data)

        mess = None

        try:
            mess = Message.deserialize(self.db)
        except:
            logger.error( "Cannot deserialize message len: {} : {}".format( len(data), data ) )

        if mess is None:
            logger.error( "Deserialization message failed" )
            self.taskSession.interpret(None)
            return

        if self.taskSession:
            for m in mess:
                self.taskSession.interpret(m)
        else:
            logger.error( "Task session for connection is None" )
            assert False

    ############################
    def fileDataReceived( self, data ):
        assert len( data ) >= 4

        self.taskSession.taskComputer.resourceManager.fileDataReceived( self.taskSession.taskId, data, self )            

    ############################
    def resultDataReceived( self, data ):
        assert len( data ) >= 4

        self.taskSession.resultDataReceived( self.taskSession.taskId, data, self )

    ############################
    def connectionLost(self, reason):
        self.opened = False

        if self.taskSession:
            self.taskSession.dropped()
