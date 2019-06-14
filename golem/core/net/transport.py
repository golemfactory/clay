from collections import namedtuple
from typing import Tuple


class LibP2PTransport:

    Host = namedtuple('Host', ['host', 'port'])

    def __init__(
        self,
        network: 'LibP2PNetwork',
        address: Tuple[str, int],
        protocol_id: int,
        peer_id: str
    ) -> None:
        self.network = network
        self.protocol_id = protocol_id
        self.peer_id = peer_id
        self.peer = self.Host(address[0], address[1])
        self._disconnecting = False

    def getPeer(self):  # noqa
        return self.peer

    @staticmethod
    def getHandle():  # noqa
        pass

    def loseConnection(self):  # noqa
        if self._disconnecting:
            return
        self._disconnecting = True
        self.network.disconnect(self.peer_id)

    def abortConnection(self):  # noqa
        self.loseConnection()

    def write(self, data: bytes) -> None:
        self.network.send(self.peer_id, self.protocol_id, data)
