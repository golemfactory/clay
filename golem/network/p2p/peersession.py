import logging

logger = logging.getLogger(__name__)

P2P_PROTOCOL_ID = 13


class PeerSessionInfo(object):

    attributes = [
        'remote_pubkey',
        'ip_port'
    ]

    def __init__(self, session):
        for attr in self.attributes:
            setattr(self, attr, getattr(session, attr))

    def get_simplified_repr(self):
        repr = self.__dict__
        return repr


class PeerMonitor(object):

    def __init__(self, peermanager):
        self.peermanager = peermanager

    def get_diagnostics(self, output_format):
        peer_data = []
        for peer in self.app.services.peermanager.peers:
            peer = PeerSessionInfo(peer).get_simplified_repr()
            peer_data.append(peer)
        return self._format_diagnostics(peer_data, output_format)

