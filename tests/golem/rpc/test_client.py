import uuid

import time

from twisted.internet import threads

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

        result = [None, None]

        def run_client():
            client = ws_client.build_client(service_info)

            def on_success(*args, **kwargs):
                result[0] = client.method_1(12)
                result[1] = True
                assert result[0] == 12

            def on_error(*args, **kwargs):
                result[0] = None
                result[1] = False

            ws_client.connect().addCallbacks(on_success, on_error)

        threads.deferToThread(run_client)

        while result[1] is None:
            time.sleep(0.1)

        assert result[0]
