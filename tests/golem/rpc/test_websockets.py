import time
import unittest
import uuid

from mock import Mock

from golem.core.simpleserializer import SimpleSerializer
from golem.rpc.websockets import WebSocketRPCServerFactory, WebSocketRPCClientFactory, MessageLedger, SessionManager
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


class TestSessionManager(unittest.TestCase):

    def test_session_lifecycle(self):
        peer = Mock()
        host, port = '127.0.0.1', 10000
        peer.host, peer.port = host, port

        session = Mock()
        session.transport.getPeer.return_value = peer

        manager = SessionManager()

        manager.add_session(session)
        assert manager.has_session(session)
        assert manager.get_session(host, port) is session
        manager.remove_session(session)
        assert manager.get_session(host, port) is None


class TestMessageLedger(unittest.TestCase):

    def test_add_clear_request(self):

        ledger = MessageLedger()
        ledger.serializer = SimpleSerializer()

        peer = Mock()
        peer.host, peer.port = '127.0.0.1', 10000

        session = Mock()
        session.transport.getPeer.return_value = peer

        message = Mock()
        message.id = 'message_id'

        no_response = (None, None)

        assert ledger.get_response(message) == no_response

        ledger.add_request(message, session)
        assert ledger.get_response(message) != no_response

        message.id = 'message_id_2'
        assert ledger.get_response(message) == no_response

        ledger.clear_request(message)
        assert ledger.get_response(message) == no_response
