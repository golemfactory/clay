import struct
from abc import ABCMeta, abstractmethod
from typing import Any, Tuple


class IPCMessageSerializer(metaclass=ABCMeta):

    ENCODING = 'utf-8'

    FORMAT_LEN = '!I'
    LENGTH_LEN = struct.calcsize(FORMAT_LEN)

    @abstractmethod
    def serialize(self, msg, **options) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes, **options) -> Any:
        pass

    def serialize_header(self, msg) -> bytes:
        name = bytes(msg.__class__.__name__, self.ENCODING)
        len_bytes = struct.pack(self.FORMAT_LEN, len(name))
        return len_bytes + name

    def deserialize_header(self, data: bytes) -> Tuple[int, str]:
        len_slice = data[:self.LENGTH_LEN]
        name_len: int = struct.unpack(self.FORMAT_LEN, len_slice)[0]
        name_bytes: bytes = data[self.LENGTH_LEN:self.LENGTH_LEN + name_len]

        offset = self.LENGTH_LEN + name_len
        name = name_bytes.decode(self.ENCODING)
        return offset, name
