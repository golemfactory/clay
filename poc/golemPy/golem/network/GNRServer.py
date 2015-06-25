import logging

from golem.network.transport.Tcp import Network

logger = logging.getLogger(__name__)

class GNRServer:
    #############################
    def __init__(self, configDesc, factory, useIp6=False):
        self.configDesc = configDesc
        self.factory = factory

        self.curPort = 0
        self.iListeningPort = None

        self._startAccepting(useIp6)

    #############################
    def newConnection(self, session):
        pass

    #############################
    def changeConfig(self, configDesc):
        self.configDesc = configDesc

        if self.iListeningPort is None:
            self._startAccepting()
            return

        if self.iListeningPort and (configDesc.startPort > self.curPort or configDesc.endPort < self.curPort):
            self.iListeningPort.stopListening()
            self._startAccepting()

    #############################
    def _startAccepting(self, useIp6=False):
        logger.info("Enabling network accepting state")

        Network.listen(self.configDesc.startPort, self.configDesc.endPort, self._getFactory(), None, self._listeningEstablished, self._listeningFailure, useIp6)

    #############################
    def _getFactory(self):
        return self.factory()

    #############################
    def _listeningEstablished(self, iListeningPort):
        self.curPort = iListeningPort.getHost().port
        self.iListeningPort = iListeningPort
        logger.info(" Port {} opened - listening".format(self.curPort))

    #############################
    def _listeningFailure(self, *args):
        logger.error("Listening on ports {} to {} failure".format(self.configDesc.startPort, self.configDesc.endPort))


