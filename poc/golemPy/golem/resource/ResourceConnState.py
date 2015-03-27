import logging
import time

from golem.Message import Message
from golem.core.databuffer import DataBuffer
from golem.network.p2p.ConnectionState import ConnectionState

logger = logging.getLogger(__name__)

class ResourceConnState( ConnectionState ):
    ############################
    def __init__( self, server = None):
        ConnectionState.__init__( self )
        self.session = None
        self.server = server
        self.fileMode = False

    ############################
    def connectionMade( self ):
        self.opened = True
        if self.server:
            from ResourceSession import ResourceSession
            self.session = ResourceSession( self )
            self.server.newConnection( self.session )

    ############################
    def setSession( self, session ):
        self.session = session

    ############################
    def dataReceived( self, data ):
        assert self.opened
        assert isinstance(self.db, DataBuffer)

        if not self.session:
            logger.warning( "No session argument in connection state" )
            return

        self.session.lastMessageTime = time.time()

        if self.fileMode:
            self.fileDataReceived( data )
            return

        self.db.appendString( data )
        mess = Message.deserialize( self.db )
        if mess is None or len( mess ) == 0:
            logger.error( "Deserialization message failed " )
            return None

        for m in mess:
            self.session.interpret( m )


    ############################
    def fileDataReceived( self, data  ):
        self.session.fileDataReceived( data )

    ############################
    def connectionLost( self, reason ):
        self.opened = False
        self.session.dropped()
