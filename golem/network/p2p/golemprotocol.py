import rlp
from devp2p.protocol import BaseProtocol, SubProtocolError
from ethereum import slogging
from rlp.sedes import big_endian_int, binary, List, CountableList
from golem.docker.image import DockerImage
from golem.task.taskbase import TaskHeader
from golem.network.p2p.node import Node

log = slogging.get_logger('golem.protocol')

class SerializedDockerImages(rlp.Serializable):
    """

    """

    def __init__(self, docker_image):
        self.id = str(docker_image.id)
        self.name = docker_image.name
        self.repository = docker_image.repository
        self.tag = docker_image.tag

    @classmethod
    def create(cls, data):
        di = DockerImage(data[2], data[0], data[3])
        return cls(di)

    fields = [
        ('id', rlp.sedes.binary),
        ('name', rlp.sedes.binary),
        ('repository', rlp.sedes.binary),
        ('tag', rlp.sedes.binary)
    ]

class SerializedTaskHeader(rlp.Serializable):
    """

    """

    def __init__(self, task_header):
        self.deadline = str(task_header.deadline)
        di = []
        for i in task_header.docker_images:
            di.append(SerializedDockerImages(i))
        self.images = di

    @classmethod
    def create(cls, data):
        di = []
        for i in data[1]:
            di.append(SerializedDockerImages.create(i))
        #just a dummy task until all values wont be serialized
        th = TaskHeader(
            node_name="node1",
            task_id="xyz",
            task_owner_address="127.0.0.1",
            task_owner_port=45000,
            task_owner_key_id="key2",
            environment="test",
            max_price=30,
            deadline=data[0],
            docker_images=di
        )
        return cls(th)

    fields = [
        ('deadline', rlp.sedes.binary),
        ('images', rlp.sedes.CountableList(SerializedDockerImages))
    ]

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
        Sens tasks descriptors
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
                theaders.append(TaskHeader.deserialize(th))

            return theaders