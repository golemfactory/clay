import time
import uuid

from golem.rpc.websockets import WebSocketRPCServerFactory, WebSocketRPCClientFactory
from golem.tools.testwithreactor import TestWithReactor


class MockService(object):

    some_property = 'Some string'

    def method_1(self, value):
        return value

    def method_2(self):
        return 2

    def __private_method(self):
        raise Exception("Should not be called")


def _build():
    mock_service = MockService()

    ws_server = WebSocketRPCServerFactory()
    ws_server.listen()

    service_info = ws_server.add_service(mock_service)

    ws_address = service_info.rpc_address
    ws_client = WebSocketRPCClientFactory(ws_address.host, ws_address.port)

    return ws_client, ws_server, service_info


class TestRPCClient(TestWithReactor):

    def setUp(self):
        big_chunk = []
        for i in xrange(0, 1000):
            big_chunk.extend(list(str(uuid.uuid4())))
        self.big_chunk = big_chunk

    def test(self):

        ws_client, ws_server, service_info = _build()
        client = ws_client.build_client(service_info)
        result = [None, None]

        def on_success(*args, **kwargs):

            def on_result(value):
                result[0] = value
                result[1] = True
                assert result[0] == self.big_chunk

            deferred = client.method_1(self.big_chunk)
            deferred.addCallback(on_result)

        def on_error(*args, **kwargs):
            result[0] = None
            result[1] = False
            self.fail("Error occurred {}".format(args))

        ws_client.connect().addCallbacks(on_success, on_error)

        while result[1] is None:
            time.sleep(1)

    def test_batch(self):

        ws_client, ws_server, service_info = _build()
        client = ws_client.build_client(service_info)
        result = [None, None]

        def on_success(*args, **kwargs):

            def on_result(value):
                result[0] = value
                result[1] = True
                assert value[0] == self.big_chunk
                assert value[1] == 2

            deferred = client.start_batch() \
                .method_1(self.big_chunk)   \
                .method_2()                 \
                .call()
            deferred.addCallback(on_result)

        def on_error(*args, **kwargs):
            result[0] = None
            result[1] = False
            self.fail("Error occurred {}".format(args))

        ws_client.connect().addCallbacks(on_success, on_error)

        while result[1] is None:
            time.sleep(1)

