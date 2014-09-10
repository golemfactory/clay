from golem.Message import Message
from golem.network.ConnectionState import ConnectionState
import logging

logger = logging.getLogger(__name__)

class ClientManagerConnState( ConnectionState ):

    ############################
    def __init__( self ):
        ConnectionState.__init__( self )
        self.clientManagerSession = None

    ############################
    def setSession( self, session ):
        self.clientManagerSession = session

    ############################
    def connectionMade( self ):
        self.opened = True

    ############################
    def dataReceived(self, data):
        assert self.opened

        self.db.appendString(data)
        mess = Message.deserialize( self.db )
        if mess is None:
            logger.error( "Deserialization message failed" )
            self.clientManagerSession.interpret( None )

        if self.clientManagerSession:
            for m in mess:
                self.clientManagerSession.interpret(m)
        else:
            logger.error( "manager session for connection is None" )
            assert False

    ############################
    def connectionLost(self, reason):
        self.opened = False
        self.clientManagerSession.dropped()
