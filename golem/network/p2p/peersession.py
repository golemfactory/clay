import logging

logger = logging.getLogger(__name__)

P2P_PROTOCOL_ID = 12


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
        #del repr['node_info']
        return repr

