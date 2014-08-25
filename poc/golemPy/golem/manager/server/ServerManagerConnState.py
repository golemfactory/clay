
from golem.Message import Message
from golem.network.ConnectionState import ConnectionState
from ServerManagerSession import ServerManagerSession
import logging

logger = logging.getLogger(__name__)

class ServerManagerConnState( ConnectionState ):

    ############################
    def __init__( self, server ):
        ConnectionState.__init__( self )
        self.server         = server
        self.managerSession = None

    ############################
    def setSession( self, session ):
        self.managerSession = session

    ############################
    def connectionMade( self ):
        self.opened = True
        pp = self.transport.getPeer()
        self.managerSession = ServerManagerSession( self, pp.host, pp.port, self.server )
        self.server.newConnection( self.managerSession )

    ############################
    def dataReceived(self, data):
        assert self.opened

        self.db.appendString(data)
        mess = Message.deserialize( self.db )
        if mess is None:
            logger.errror( "Deserialization message failed" )
            self.managerSession.interpret( None )

        if self.managerSession:
            for m in mess:
                self.managerSession.interpret(m)
        else:
            logger.error( "manager session for connection is None" )
            assert False

    ############################
    def connectionLost(self, reason):
        self.opened = False
        self.managerSession.dropped()
