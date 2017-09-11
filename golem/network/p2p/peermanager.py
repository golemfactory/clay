import devp2p
from devp2p.p2p_protocol import P2PProtocol
from devp2p.peermanager import PeerManager, log

from golem.network.p2p.peer import GolemPeer, COMPUTATION_CAPABILITY

# Patch the default Peer class
devp2p.peermanager.Peer = GolemPeer


class GolemPeerManager(PeerManager):

    def __init__(self, app):
        super().__init__(app)
        self._computation = 0

    @property
    def computation_capability(self):
        return self._computation

    @computation_capability.setter
    def computation_capability(self, value):
        self._computation = 1 if value else 0

    def on_hello_received(self, proto, version, client_version_string,
                          capabilities, listen_port, remote_pubkey):

        log.debug('hello_received', peer=proto.peer, num_peers=len(self.peers))

        max_peers = self.config['p2p']['max_peers']
        pub_keys = [p.remote_pubkey for p in self.peers if p != proto.peer]

        if remote_pubkey in pub_keys:
            log.debug('connected to that node already')
            proto.send_disconnect(proto.disconnect.reason.already_connected)
            return False

        # Look for the 'computation' capability. If found, we can bypass
        # the current upper connection limit.
        for name, _ in capabilities:
            if name == COMPUTATION_CAPABILITY:
                log.debug('computing node connected', max=max_peers)
                return True

        if len(self.peers) > max_peers:
            log.debug('too many peers', max=max_peers)
            proto.send_disconnect(proto.disconnect.reason.too_many_peers)
            return False

        return True

    @staticmethod
    def disconnect(peer,
                   reason=P2PProtocol.disconnect.reason.disconnect_requested):

        for protocol in peer.protocols:
            if protocol.name == 'p2p':
                log.debug('disconnecting', peer=peer)
                protocol.send_disconnect(reason)
                return True
        return False

    def __copy__(self):
        new = type(self)(self.app)
        new.__dict__.update(self.__dict__)
        return new
