import time
from typing import Optional

from .modelbase import BasicModel


class PingModel(BasicModel):  # pylint: disable=too-few-public-methods
    TYPE = "PingModel"

    def __init__(self, sessid,
                 ports: tuple, timestamp: Optional[float] = None) -> None:
        super().__init__(self.TYPE, sessid)
        self.ports = ports
        self.timestamp = timestamp if timestamp else time.time()
