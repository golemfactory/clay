import unittest
from contextlib import contextmanager

from golem.interface.websockets import WebSocketCLI
from golem.rpc.legacy.websockets import WebSocketRPCClientFactory
from mock import Mock, patch
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure


class TestWebSocketCLI(unittest.TestCase):

    @patch('twisted.internet.threads', create=True, new_callable=Mock)
    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_execute(self, reactor, threads):

        deferred = Deferred()
        deferred.result = "Success"
        deferred.called = True

        reactor.callWhenRunning = lambda m, *a, **kw: m(*a, **kw)

        @contextmanager
        def rpc_context():
            connect = WebSocketRPCClientFactory.connect
            build_simple_client = WebSocketRPCClientFactory.build_simple_client

            WebSocketRPCClientFactory.connect = Mock()
            WebSocketRPCClientFactory.connect.return_value = deferred
            WebSocketRPCClientFactory.build_simple_client = Mock()
            WebSocketRPCClientFactory.build_simple_client.return_value = Mock()

            yield

            WebSocketRPCClientFactory.connect = connect
            WebSocketRPCClientFactory.build_simple_client = build_simple_client

        with rpc_context():

            ws_cli = WebSocketCLI(Mock(), '127.0.0.1', '12345')
            ws_cli.execute()

            assert isinstance(ws_cli.cli.register_client.call_args_list[0][0][0], Mock)

        with rpc_context():

            deferred.result = Failure(Exception("Failure"))
            deferred.called = True

            ws_cli = WebSocketCLI(Mock(), '127.0.0.1', '12345')
            ws_cli.execute()

            assert isinstance(ws_cli.cli.register_client.call_args_list[0][0][0], WebSocketCLI.NoConnection)

    def test_no_connection(self):

        client = WebSocketCLI.NoConnection()

        with self.assertRaises(Exception):
            client.account()

        with self.assertRaises(Exception):
            client.some_unknown_method()
