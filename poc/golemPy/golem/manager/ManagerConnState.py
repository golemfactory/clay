import logging

from golem.network.transport.tcp_network import ServerProtocol
from golem.Message import Message


logger = logging.getLogger(__name__)


class ManagerConnState(ServerProtocol):
    def __init__(self, server=None):
        ServerProtocol.__init__(self, server)

    def setSession(self, session):
        self.session = session

    ############################
    def connectionMade(self):
        self.opened = True

        if self.server:
            from golem.manager.server.ServerManagerSession import ServerManagerSession
            pp = self.transport.getPeer()
            self.session = ServerManagerSession(self, pp.host, pp.port, self.server)
            self.server.newConnection(self.session)

    ############################
    def dataReceived(self, data):
        assert self.opened

        self.db.appendString(data)
        mess = Message.deserialize(self.db)
        if mess is None:
            logger.error("Deserialization message failed")
            self.session.interpret(None)

        if self.session:
            for m in mess:
                self.session.interpret(m)
        else:
            logger.error("Session for connection is None")
            assert False

    ############################
    def connectionLost(self, reason):
        self.opened = False
        if self.session:
            self.session.dropped()
        else:
            logger.error("Session for connection is None")

        logger.warning("Connection lost: {}".format(reason))