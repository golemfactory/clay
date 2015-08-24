import logging

from golem.network.transport.tcp_server import TCPServer
from golem.network.transport.tcp_network import TCPNetwork, SafeProtocol
from golem.network.transport.network import ProtocolFactory, SessionFactory
from PeerSession import PeerSession

logger = logging.getLogger(__name__)


class P2PServer(TCPServer):
    def __init__(self, config_desc, p2p_service=None, use_ipv6=False):
        network = TCPNetwork(ProtocolFactory(SafeProtocol, p2p_service, SessionFactory(PeerSession)), use_ipv6)
        TCPServer.__init__(self, config_desc, network)
        self.p2p_service = p2p_service

    def encrypt(self, msg, publicKey):
        return self.p2p_service.encrypt(msg, publicKey)

    def decrypt(self, msg):
        return self.p2p_service.decrypt(msg)

    def removePeer(self, session):
        self.p2p_service.removePeer(session)
