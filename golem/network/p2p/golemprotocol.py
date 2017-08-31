import rlp
from devp2p.protocol import BaseProtocol
from ethereum import slogging

from golem.task.taskbase import TaskHeader

log = slogging.get_logger('golem.protocol')


class GolemProtocol(BaseProtocol):
    protocol_id = 18317  # just a random number; not sure what to put here
    name = b'golem_proto'

    def __init__(self, peer, service):
        # required by P2PProtocol
        self.config = peer.config
        BaseProtocol.__init__(self, peer, service)

    class get_tasks(BaseProtocol.command):
        """
        Peer want tasks information
        """
        cmd_id = 0

        structure = []

    class task_headers(BaseProtocol.command):
        """
        Sends tasks descriptors
        """
        cmd_id = 1

        structure = rlp.sedes.CountableList(TaskHeader)

        def create(self, proto, *args, **kwargs):
            return list(args[0])

        @classmethod
        def decode_payload(cls, rlp_data):
            return [TaskHeader.deserialize(task_header, mutable=True)
                    for task_header in rlp.decode_lazy(rlp_data)]

    class remove_task(BaseProtocol.command):
        """
        Remove given task from p2p network
        """
        cmd_id = 2

        structure = [('task_id', rlp.sedes.binary)]

    class get_node_name(BaseProtocol.command):
        """
        Request node name
        """
        cmd_id = 3

        structure = []

    class node_name(BaseProtocol.command):
        """
        Deliver node name
        """
        cmd_id = 4

        structure = [('node_name', rlp.sedes.binary)]
