import unittest

from golem.ipc.messages.ttypes import Wrapper
from golem.ipc.serializer.thrift import ThriftMessageSerializer


class TestThriftSerializer(unittest.TestCase):

    def test_message_serialization(self):
        msg_types = {'Wrapper': Wrapper}
        src_message = Wrapper(msg_name="ignored",
                              msg_bytes=b'012',
                              request_id=b'022')

        serializer = ThriftMessageSerializer()
        serialized = serializer.serialize(src_message, request_id=b'021')
        request_id, deserialized = serializer.deserialize(serialized, msg_types)

        assert request_id == b'021'
        assert src_message.__dict__ == deserialized.__dict__
