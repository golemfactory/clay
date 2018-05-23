import struct
from abc import ABCMeta, abstractmethod
from typing import Tuple, Any


class IPCMessageSerializer(metaclass=ABCMeta):

    # Header:
    # request_id_len | request_id (bytes) |
    # msg_name_len | msg_name (str as bytes)

    ENCODING = 'utf-8'

    FORMAT_LEN = '!I'
    LENGTH_LEN = struct.calcsize(FORMAT_LEN)

    @abstractmethod
    def serialize(self,
                  msg: Any,
                  request_id: bytes = b'',
                  **options) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes, **options) -> Tuple[bytes, object]:
        pass

    def serialize_header(self,
                         msg: object,
                         request_id: bytes) -> bytes:

        request_id_bytes = self._serialize_bytes(request_id)
        name_bytes = self._serialize_str(msg.__class__.__name__)

        return request_id_bytes + name_bytes

    def deserialize_header(self, buf: bytes) -> Tuple[bytes, int, str]:
        request_id_offset, request_id = self._deserialize_bytes(buf)
        name_offset, name = self._deserialize_str(buf[request_id_offset:])

        offset = request_id_offset + name_offset
        return request_id, offset, name

    def _serialize_str(self, string: str) -> bytes:
        str_bytes = bytes(string, self.ENCODING)
        return self._serialize_bytes(str_bytes)

    def _serialize_bytes(self, buf: bytes) -> bytes:
        len_bytes = struct.pack(self.FORMAT_LEN, len(buf))
        return len_bytes + buf

    def _deserialize_str(self, buf: bytes) -> Tuple[int, str]:
        offset, str_bytes = self._deserialize_bytes(buf)
        return offset, str_bytes.decode(self.ENCODING)

    def _deserialize_bytes(self, buf: bytes) -> Tuple[int, bytes]:
        len_slice = buf[:self.LENGTH_LEN]
        str_len: int = struct.unpack(self.FORMAT_LEN, len_slice)[0]
        str_bytes: bytes = buf[self.LENGTH_LEN:self.LENGTH_LEN + str_len]

        offset = self.LENGTH_LEN + str_len
        return offset, str_bytes
