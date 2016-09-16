import unittest

import StringIO
from contextlib import contextmanager

from golem.rpc.websockets import WebSocketRPCClientFactory
from twisted.python.failure import Failure

from mock import Mock, patch, MagicMock
from twisted.internet.defer import Deferred

from golem.interface.websockets import WebSocketCLI


class TestWebSocketCLI(unittest.TestCase):

    @patch('twisted.internet.threads', create=True, new_callable=Mock)
    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_execute(self, reactor, threads):

        cli_class = Mock
        cli_class.execute = Mock()

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

            ws_cli = WebSocketCLI(cli_class, '127.0.0.1', '12345')
            ws_cli.execute()

            assert ws_cli.cli

        with rpc_context():

            deferred.result = Failure(Exception("Failure"))
            deferred.called = True

            ws_cli = WebSocketCLI(cli_class, '127.0.0.1', '12345')
            ws_cli.execute()
            assert not ws_cli.cli
