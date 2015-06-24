import logging

from golem.network.p2p.NetConnState import NetConnState
from golem.network.GNRServer import GNRServer


logger = logging.getLogger(__name__)

#######################################################################################
class P2PServer(GNRServer):
    #############################
    def __init__(self, configDesc, p2pService=None, useIp6=False):

        self.p2pService = p2pService
        GNRServer.__init__(self, configDesc, NetServerFactory, useIp6)

    #############################
    def newConnection(self, session):
        self.p2pService.newSession(session)

    #############################
    def encrypt(self, msg, publicKey):
        return self.p2pService.encrypt(msg, publicKey)

    #############################
    def decrypt(self, msg):
        return self.p2pService.decrypt(msg)

    #############################
    def _getFactory(self):
        return self.factory(self)

#######################################################################################

from twisted.internet.protocol import Factory

from golem.network.p2p.PeerSession import PeerSessionFactory

class NetServerFactory(Factory):
    #############################
    def __init__(self, p2pserver):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol(self, addr):
        logger.info("Protocol build for {}".format(addr))
        protocol = NetConnState(self.p2pserver)
        protocol.setSessionFactory(PeerSessionFactory())
        return protocol

