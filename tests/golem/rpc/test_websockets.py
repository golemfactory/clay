import time
import unittest
import uuid
from mock import Mock

from twisted.internet.defer import Deferred

from golem.core.simpleserializer import SimpleSerializer
from golem.rpc.messages import RPCRequestMessage
from golem.rpc.service import RPC
from golem.rpc.websockets import WebSocketRPCServerFactory, WebSocketRPCClientFactory, MessageLedger, SessionManager, \
    WebSocketRPCProtocol
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

        started = time.time()
        while result[1] is None:
            time.sleep(0.2)
            if time.time() - started > 10:
                self.fail("Test timeout")

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

        started = time.time()
        while result[1] is None:
            time.sleep(0.2)
            if time.time() - started > 10:
                self.fail("Test timeout")

    def test_wait_for_session(self):
        rpc = RPC.__new__(RPC)
        rpc.reactor = self.reactor_thread.reactor
        rpc.retry_timeout = 0.1
        rpc.conn_timeout = 0.1
        rpc.factory = Mock()
        rpc.factory.get_session.return_value = None

        def fail(*args):
            self.fail("Invalid callback")

        deferred = rpc._wait_for_session('localhost', 1234)
        deferred.addCallback(fail)

        deferred = rpc.factory.get_session.return_value = Mock()
        deferred.addErrback(fail)

    def test_add_session(self):
        peer = Mock()
        peer.host, peer.port = '127.0.0.1', 10000

        factory = WebSocketRPCClientFactory(peer.host, peer.port)
        factory._deferred = Deferred()

        session = Mock()
        session.transport.getPeer.return_value = peer

        factory.add_session(session)
        assert factory._deferred.called
        # deferred raises an exception on second cb call
        factory.add_session(session)

    def test_reconnect(self):

        ws_client, ws_server, service_info = _build()
        client = ws_client.build_client(service_info)
        result = [None, None]
        reconnect = [True]

        def on_success(*args, **kwargs):
            if reconnect[0]:
                reconnect[0] = False
                ws_client.connector.disconnect()

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

        started = time.time()
        while result[1] is None:
            time.sleep(0.2)
            if time.time() - started > 15:
                self.fail("Test timed out")

        ws_client._deferred = Deferred()
        ws_client.clientConnectionFailed(Mock(), Mock())


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

        no_response = None

        assert ledger.get_response(message) == no_response

        ledger.add_request(message, session)
        assert ledger.get_response(message) != no_response

        ledger.remove_request(message)
        assert ledger.get_response(message) == no_response

        ledger.add_request(message, session)
        message.id = 'message_id_2'
        assert ledger.get_response(message) == no_response

    def test_add_response(self):

        ledger = MessageLedger()
        ledger.serializer = SimpleSerializer()

        peer = Mock()
        peer.host, peer.port = '127.0.0.1', 10000

        session = Mock()
        session.transport.getPeer.return_value = peer

        message = Mock()
        message.id = 'message_id'

        response = Mock()
        response.id = 'response_id'
        response.request_id = message.id

        ledger.add_request(message, session)

        entry = ledger.get_response(message)
        deferred = entry['deferred']

        ledger.add_response(response)
        assert deferred.called
        ledger.add_response(response)


class TestProtocol(unittest.TestCase):

    def test_send_message(self):

        def failing_func(*args, **kwargs):
            raise Exception()

        factory = WebSocketRPCClientFactory('localhost', 1234)
        factory.perform_request = Mock()

        protocol = WebSocketRPCProtocol()
        protocol.transport = Mock()
        protocol.factory = factory
        protocol.sendMessage = Mock()

        message = RPCRequestMessage('test', [], {})

        protocol.send_message(message, new_request=False)
        assert message.id not in factory.requests

        protocol.send_message(message, new_request=True)
        assert message.id in factory.requests

        factory.remove_request(message)
        assert message.id not in factory.requests

        factory.prepare_message = failing_func

        protocol.send_message(message, new_request=False)
        assert message.id not in factory.requests

        protocol.send_message(message, new_request=True)
        assert message.id not in factory.requests


