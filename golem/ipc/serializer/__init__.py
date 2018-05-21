import struct
from abc import ABCMeta, abstractmethod
from typing import Any, Tuple


class IPCMessageSerializer(metaclass=ABCMeta):

    ENCODING = 'utf-8'

    FORMAT_LEN = '!I'
    FORMAT_NAME = '{}s'

    LENGTH_LEN = struct.calcsize(FORMAT_LEN)

    @abstractmethod
    def serialize(self, msg, **options) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes, **options) -> Any:
        pass

    def serialize_header(self, msg) -> bytes:

        name = bytes(msg.__class__.__name__, self.ENCODING)
        name_len = len(name)

        len_bytes = struct.pack(self.FORMAT_LEN, name_len)
        name_bytes = struct.pack(self.FORMAT_NAME.format(name_len), name)

        return len_bytes + name_bytes

    def deserialize_header(self, data: bytes) -> Tuple[int, str]:

        name_len: int = struct.unpack(self.FORMAT_LEN, data[:self.LENGTH_LEN])
        name_bytes: bytes = struct.unpack(self.FORMAT_NAME.format(name_len),
                                          data[self.LENGTH_LEN:])

        return name_len, name_bytes.decode(self.ENCODING)
