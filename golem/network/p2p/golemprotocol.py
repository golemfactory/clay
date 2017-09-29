import itertools
import rlp
from ethereum import slogging

from golem.core.simpleserializer import CBORSedes
from golem.network.p2p.protocol import SigningProtocol

log = slogging.get_logger('golem.protocol')


class GolemProtocol(SigningProtocol):
    protocol_id = 18317  # just a random number; not sure what to put here
    version = 1
    name = b'golem_proto'

    def __init__(self, peer, service):
        # required by P2PProtocol
        self.config = peer.config
        SigningProtocol.__init__(self, peer, service)

    class get_tasks(SigningProtocol.command):
        """
        Peer want tasks information
        """
        cmd_id = 0

        structure = []

    class task_headers(SigningProtocol.command):
        """
        Sends tasks descriptors
        """
        cmd_id = 1

        structure = rlp.sedes.CountableList(CBORSedes)

        def received(self, decoded):
            if isinstance(decoded, tuple):
                # flatten the contents
                return list(itertools.chain.from_iterable(decoded))
            return []

    class remove_task(SigningProtocol.command):
        """
        Remove given task from p2p network
        """
        cmd_id = 2

        structure = [('task_id', rlp.sedes.binary)]

    class get_node_name(SigningProtocol.command):
        """
        Request node name
        """
        cmd_id = 3

        structure = []

    class node_name(SigningProtocol.command):
        """
        Deliver node name
        """
        cmd_id = 4

        structure = [('node_name', rlp.sedes.binary)]
