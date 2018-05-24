from abc import ABCMeta, abstractmethod
from typing import Tuple, Any


class IPCMessageSerializer(metaclass=ABCMeta):

    @abstractmethod
    def serialize(self, msg: Any, request_id: bytes = b'', **options) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, buf: bytes, **options) -> Tuple[bytes, object]:
        pass
