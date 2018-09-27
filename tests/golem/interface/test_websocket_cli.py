from contextlib import contextmanager
import unittest
from unittest.mock import Mock, patch, MagicMock

from golem.interface.websockets import WebSocketCLI
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP
from golem.rpc.session import Session, Client
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure


class TestWebSocketCLI(unittest.TestCase):

    @patch('twisted.internet.threads', create=True, new_callable=Mock)
    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_execute(self, reactor, _):

        deferred = Deferred()
        deferred.result = "Success"
        deferred.called = True

        reactor.callWhenRunning = lambda m, *a, **kw: m(*a, **kw)

        @contextmanager
        def rpc_context():
            connect = Session.connect
            Session.connect = Mock()
            Session.connect.return_value = deferred
            yield
            Session.connect = connect

        with rpc_context():

            ws_cli = WebSocketCLI(Mock(),
                                  MagicMock(),
                                  '127.0.0.1',
                                  12345,
                                  realm='golem')
            ws_cli.execute()

            assert isinstance(
                ws_cli.cli.register_client.call_args_list[0][0][0],
                Client
            )

        with rpc_context():

            deferred.result = Failure(Exception("Failure"))
            deferred.called = True

            ws_cli = WebSocketCLI(Mock(),
                                  MagicMock(),
                                  '127.0.0.1',
                                  12345,
                                  realm='golem')
            ws_cli.execute()

            assert isinstance(
                ws_cli.cli.register_client.call_args_list[0][0][0],
                WebSocketCLI.NoConnection
            )

    def test_no_connection(self):

        client = WebSocketCLI.NoConnection()

        with self.assertRaises(Exception):
            client.account()

        with self.assertRaises(Exception):
            client.some_unknown_method()

    @patch('twisted.internet.reactor', create=True)
    @patch('golem.interface.websockets.Client._call')
    def test_client(self, call, reactor):

        def success(*_a, **_kw):
            _deferred = Deferred()
            _deferred.callback(True)
            return _deferred

        reactor.callFromThread.side_effect = lambda x: x()
        client = WebSocketCLI.CLIClient(session=Mock(),
                                        method_map=CORE_METHOD_MAP)

        call.side_effect = success

        deferred = client._call('ui.stop')
        assert reactor.callFromThread.called
        assert deferred.called
        assert deferred.result is True

        reactor.callFromThread.reset_mock()
        call.side_effect = Exception

        deferred = client._call('ui.stop')
        assert reactor.callFromThread.called
        assert deferred.called
        assert isinstance(deferred.result, Failure)
