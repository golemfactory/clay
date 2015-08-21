import logging

from golem.network.transport.tcp_server import TCPServer
from golem.network.transport.tcp_network import TCPNetwork, SafeProtocol
from golem.network.transport.network import ProtocolFactory
from golem.network.p2p.PeerSession import PeerSessionFactory

logger = logging.getLogger(__name__)


class P2PServer(TCPServer):
    def __init__(self, config_desc, p2p_service=None, use_ipv6=False):
        network = TCPNetwork(ProtocolFactory(SafeProtocol, p2p_service, PeerSessionFactory()), use_ipv6)
        TCPServer.__init__(self, config_desc, network)
        self.p2pservice = p2p_service

    def encrypt(self, msg, publicKey):
        return self.p2pService.encrypt(msg, publicKey)

    def decrypt(self, msg):
        return self.p2pService.decrypt(msg)

    def removePeer(self, session):
        self.p2pservice.removePeer(session)
