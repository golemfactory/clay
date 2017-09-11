from devp2p.peer import Peer


COMPUTATION_CAPABILITY = 'computation'


class GolemPeer(Peer):

    @property
    def capabilities(self):
        capabilities = super().capabilities
        if self.peermanager.computation_capability:
            capabilities += [(COMPUTATION_CAPABILITY, 1)]
        return capabilities

    @property
    def computation_capability(self):
        return bool(self.peermanager.computation_capability)
