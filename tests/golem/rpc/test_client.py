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


class TestRPCClient(TestWithReactor):

    def test(self):

        big_chunk = []

        for i in xrange(0, 1000):
            big_chunk.extend(list(str(uuid.uuid4())))

        mock_service = MockService()

        ws_server = WebSocketRPCServerFactory()
        ws_server.listen()
        service_info = ws_server.add_service(mock_service)

        ws_address = service_info.ws_address
        ws_client = WebSocketRPCClientFactory(ws_address.host, ws_address.port)

        client = ws_client.build_client(service_info)
        result = [None, None]

        def on_success(*args, **kwargs):

            def on_result(value):
                result[0] = value
                result[1] = True
                assert result[0] == big_chunk

            deferred = client.method_1(big_chunk)
            deferred.addCallback(on_result)

        def on_error(*args, **kwargs):
            result[0] = None
            result[1] = False
            self.fail("Error occurred {}".format(args))

        ws_client.connect().addCallbacks(on_success, on_error)

        while result[1] is None:
            time.sleep(1)


