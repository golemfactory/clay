import rlp
from devp2p.protocol import BaseProtocol


class GolemProtocol(BaseProtocol):
    """Golem Wire Protocol"""

    protocol_id = 1
    network_id = 0
    max_cmd_id = 15  # FIXME
    name = 'golem'
    version = 1

    def __init__(self, peer, service):
        self.config = peer.config  # Required by BaseProtocol FIXME: Check it
        super(GolemProtocol, self).__init__(peer, service)

    class status(BaseProtocol.command):
        """
        protocol_version: The version of the protocol the peer implements.
        """
        cmd_id = 0

        structure = [
            # FIXME: Protocol version is not needed here.
            # DEVp2p have that information.
            ('protocol_version', rlp.sedes.big_endian_int)
        ]

        def create(self, proto):
            return [proto.version]
