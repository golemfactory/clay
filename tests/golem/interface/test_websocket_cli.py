from contextlib import contextmanager
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
import unittest
import unittest.mock as mock

from golem.interface.websockets import WebSocketCLI
from golem.rpc.session import Session, Client


class TestWebSocketCLI(unittest.TestCase):

    @mock.patch('twisted.internet.threads', create=True, new_callable=mock.Mock)
    @mock.patch('twisted.internet.reactor', create=True, new_callable=mock.Mock)
    def test_execute(self, reactor, _):

        deferred = Deferred()
        deferred.result = "Success"
        deferred.called = True

        reactor.callWhenRunning = lambda m, *a, **kw: m(*a, **kw)

        @contextmanager
        def rpc_context():
            connect = Session.connect
            Session.connect = mock.Mock()
            Session.connect.return_value = deferred
            yield
            Session.connect = connect

        with rpc_context():

            ws_cli = WebSocketCLI(mock.Mock(), '127.0.0.1', '12345', realm='golem')
            ws_cli.execute()

            assert isinstance(ws_cli.cli.register_client.call_args_list[0][0][0], Client)

        with rpc_context():

            deferred.result = Failure(Exception("Failure"))
            deferred.called = True

            ws_cli = WebSocketCLI(mock.Mock(), '127.0.0.1', '12345', realm='golem')
            ws_cli.execute()

            assert isinstance(ws_cli.cli.register_client.call_args_list[0][0][0], WebSocketCLI.NoConnection)

    def test_no_connection(self):

        client = WebSocketCLI.NoConnection()

        with self.assertRaises(Exception):
            client.account()

        with self.assertRaises(Exception):
            client.some_unknown_method()
