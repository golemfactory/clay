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

        service = MockService()
        server = JsonRPCServer.listen(service)
        client = JsonRPCClient(service, server.url)

        assert client.method_1(123) == 123
        assert client.some_property is None
