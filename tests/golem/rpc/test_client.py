import uuid

from golem.rpc.client import JsonRPCClient
from golem.rpc.server import JsonRPCServer
from golem.tools.testwithreactor import TestWithReactor


class MockService(object):

    some_property = 'Some string'

    def method_1(self, value):
        return value

    def method_2(self):
        return 2

    def __private_method(self):
        raise Exception("Should not be called")


class TestRPCClient(TestWithReactor):

    def test(self):

        big_chunk = []

        for i in xrange(0, 1000):
            big_chunk.extend(list(str(uuid.uuid4())))

        service = MockService()
        server = JsonRPCServer.listen(service)
        client = JsonRPCClient(service, server.url)

        assert client.method_1(123) == 123
        assert client.method_1(big_chunk) == big_chunk
        assert client.some_property is None
