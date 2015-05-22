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
            if self.peer and self.peer.p2pService:
                mess = Message.decryptAndDeserialize(self.db, self.peer.p2pService, self.peer.clientKeyId)
            else:
                mess = Message.deserialize( self.db )
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

    ############################
    def sendMessage(self, msg):
        if self.peer is None or self.peer.p2pService is None:
            logger.error("Wrong session, not sending message")
            return False

        if not self.opened:
            logger.error( msg )
            logger.error( "sendMessage failed - connection closed." )
            return False

        msg.sign(self.peer.p2pService)
        serMsg = msg.serialize()
        decMsg = self.peer.p2pService.encrypt( serMsg, self.peer.clientKeyId )

        db = DataBuffer()
        db.appendLenPrefixedString( decMsg )
        self.transport.getHandle()
        self.transport.write( db.readAll() )

        return True