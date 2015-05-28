import logging

from golem.Message import Message

from golem.core.databuffer import DataBuffer

from golem.network.p2p.ConnectionState import ConnectionState

logger = logging.getLogger(__name__)

class NetConnState( ConnectionState ):
    ############################
    def __init__( self, server = None ):
        ConnectionState.__init__( self )
        self.sessionFactory = None
        self.server = server

    ############################
    def setSessionFactory(self, sessionFactory):
        self.sessionFactory = sessionFactory

    ############################
    def connectionMade(self):
        ConnectionState.connectionMade(self)

        if not self.server:
            return

        self.session = self.sessionFactory.getSession( self )
        self.server.newConnection( self.session )

    ############################
    def _prepareMsgToSend(self, msg):
        if self.session is None:
            logger.error("Wrong session, not sending message")
            return None

        msg = self.session.sign(msg)
        if not msg:
            logger.error("Wrong session, not sending message")
            return None
        serMsg = msg.serialize()
        encMsg = self.session.encrypt( serMsg )

        db = DataBuffer()
        db.appendLenPrefixedString( encMsg )
        return db.readAll()

    ############################
    def _canReceive(self):
        assert self.opened
        assert isinstance(self.db, DataBuffer)

        if not self.session and self.server:
            self.opened = False
            raise Exception('Peer for connection is None')

        return True

    ############################
    def _dataToMessages(self):
        assert isinstance( self.db, DataBuffer )
        msgs = [ msg for msg in self.db.getLenPrefixedString() ]
        messages = []
        for msg in msgs:
            decMsg = self.session.decrypt(msg)
            m = Message.deserializeMessage(decMsg)
            m.encrypted = decMsg != msg
            messages.append(m)
        return messages