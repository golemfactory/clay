import logging

from golem.Message import Message
from golem.network.p2p.ConnectionState import ConnectionState
from golem.core.databuffer import DataBuffer


logger = logging.getLogger(__name__)

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
            from golem.network.p2p.PeerSession import PeerSession
            pp = self.transport.getPeer()
            self.peer = PeerSession( self )
            self.server.newConnection( self.peer )

    ############################
    def dataReceived(self, data):
        assert self.opened
        assert isinstance(self.db, DataBuffer)

        if self.peer:
            self.db.appendString(data)
            mess = Message.deserialize(self.db)
            if mess is None or len(mess) == 0:
                logger.error( "Deserialization message failed" )
                return None

            for m in mess:
                self.peer.interpret(m)
        elif self.server:
            self.opened = False
            logger.error( "Peer for connection is None" )
            assert False
        else:
            pass

    ############################
    def connectionLost(self, reason):
        self.opened = False
        self.peer.dropped()
