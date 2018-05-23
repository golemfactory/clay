from typing import Any, Optional, Dict, Tuple

from thrift.protocol import TBinaryProtocol
from thrift.protocol.TProtocol import TProtocolFactory
from thrift.transport import TTransport

from . import IPCMessageSerializer


class ThriftMessageSerializer(IPCMessageSerializer):

    def __init__(self,
                 protocol_factory: Optional[TProtocolFactory] = None,
                 ) -> None:

        super().__init__()
        self.protocol_factory = protocol_factory or self._default_factory()

    @staticmethod
    def _default_factory():
        return TBinaryProtocol.TBinaryProtocolFactory()

    def serialize(self,
                  msg: Any,
                  request_id: bytes = b'',
                  **_options) -> bytes:

        msg.validate()

        transport = TTransport.TMemoryBuffer()
        protocol = self.protocol_factory.getProtocol(transport)

        msg.write(protocol)
        serialized = transport.getvalue()

        return self.serialize_header(msg, request_id) + serialized

    def deserialize(self,
                    data: bytes,
                    msg_types: Optional[Dict[str, Any]] = None,
                    **_options) -> Tuple[bytes, object]:

        request_id, offset, cls_name = self.deserialize_header(data)

        msg_type = msg_types[cls_name]

        transport = TTransport.TMemoryBuffer(data[offset:])
        protocol = self.protocol_factory.getProtocol(transport)

        ret = msg_type()
        ret.read(protocol)
        return request_id, ret
