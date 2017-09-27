from devp2p import utils
from devp2p.discovery import NodeDiscovery, DiscoveryProtocol, log
from devp2p.service import BaseService


class GolemDiscoveryProtocol(DiscoveryProtocol):

    version = 9010

    def __init__(self, app, transport):
        super().__init__(app, transport)
        self.verified_nodes = set()

        for bootstrap in app.config['discovery']['bootstrap_nodes']:
            ip, port, pubkey = utils.host_port_pubkey_from_uri(bootstrap)
            self.verified_nodes.add(pubkey)

    def recv_neighbours(self, nodeid, payload, mdc):
        if nodeid in self.verified_nodes:
            super().recv_neighbours(nodeid, payload, mdc)
        else:
            log.debug('Ignoring neighbours message', sender=nodeid)


class GolemNodeDiscovery(NodeDiscovery):

    def __init__(self, app):
        BaseService.__init__(self, app)
        self.protocol = GolemDiscoveryProtocol(app=self.app,
                                               transport=self)

