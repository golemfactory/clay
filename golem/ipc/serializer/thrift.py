from typing import Any, Optional, Dict, Tuple, Type

from thrift.protocol import TBinaryProtocol
from thrift.protocol.TProtocol import TProtocolFactory
from thrift.transport import TTransport

from golem.ipc.messages.ttypes import Wrapper
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

        msg_bytes = self._serialize_message(msg)
        wrapper = Wrapper(
            msg_name=msg.__class__.__name__,
            msg_bytes=msg_bytes,
            request_id=request_id
        )

        return self._serialize_message(wrapper)

    def deserialize(self,
                    buf: bytes,
                    msg_types: Optional[Dict[str, Any]] = None,
                    **_options) -> Tuple[bytes, object]:

        wrapper = self._deserialize_message(buf, Wrapper)
        msg_cls = msg_types[wrapper.msg_name]
        msg = self._deserialize_message(wrapper.msg_bytes, msg_cls)

        return wrapper.request_id, msg

    def _serialize_message(self, msg: Any) -> bytes:
        msg.validate()

        transport = TTransport.TMemoryBuffer()
        protocol = self.protocol_factory.getProtocol(transport)

        msg.write(protocol)
        return transport.getvalue()

    def _deserialize_message(self, buf: bytes, msg_cls: Type) -> Any:
        transport = TTransport.TMemoryBuffer(buf)
        protocol = self.protocol_factory.getProtocol(transport)

        msg = msg_cls()
        msg.read(protocol)
        return msg
