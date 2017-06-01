import rlp
from devp2p.protocol import BaseProtocol, SubProtocolError
from ethereum import slogging
from rlp.sedes import big_endian_int, binary, List, CountableList
from golem.docker.image import DockerImage
from golem.task.taskbase import TaskHeader
from golem.network.p2p.node import Node
from golem.core.simpleserializer import CBORSedes
log = slogging.get_logger('golem.protocol')


class GolemProtocol(BaseProtocol):
    protocol_id = 18317  # just a random number; not sure what to put here

    def __init__(self, peer, service):
        # required by P2PProtocol
        self.config = peer.config
        BaseProtocol.__init__(self, peer, service)

    class get_tasks(BaseProtocol.command):
        """
        Peer want tasks information
        """
        cmd_id = 0

        structure = [
        ]

    class task_headers(BaseProtocol.command):
        """
        Sends tasks descriptors
        """
        cmd_id = 1

        structure = rlp.sedes.CountableList(TaskHeader)

        def create(self, proto, task_headers):
            self.sent = True
            t = []
            for th in task_headers:
                t.append(th)
            return t

        @classmethod
        def decode_payload(cls, rlp_data):
            ll = rlp.decode_lazy(rlp_data)
            theaders = []
            for th in ll:
                theaders.append(TaskHeader.deserialize(th, mutable=True))

            return theaders

    class want_to_start_task_session(BaseProtocol.command):
        """
        Send invitation for connection if requestor is behind NAT
        """

        cmd_id = 2

        structure = [('node', Node),
                     ('connection_id', rlp.sedes.binary),
                     ('super_node', CBORSedes)
                     ]

    class set_task_session(BaseProtocol.command):
        """
        Someone else is trying to connect with node to which direct connection is impossible
        and to which there is no p2p connection. Send this messages to neighboring nodes in order to forward it
        to reach recipient.
        """

        cmd_id = 3

        structure = [('key', rlp.sedes.binary),
                     ('node', Node),
                     ('connection_id', rlp.sedes.binary),
                     ('super_node', CBORSedes)
                     ]

    class remove_task(BaseProtocol.command):
        """
        Remove given task from p2p network
        """
        cmd_id = 4

        structure = [('task_id', rlp.sedes.binary)]