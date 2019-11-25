# pylint: disable=protected-access,no-self-use
import unittest
from unittest.mock import Mock, patch

import autobahn
from twisted.internet import defer

from golem.rpc import session as rpc_session
from golem.rpc import utils as rpc_utils
from golem.rpc.session import (
    logger,
    Publisher,
    RPCAddress,
    Session,
    WebSocketAddress,
)
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithreactor import TestWithReactor


class TestRPCAddress(unittest.TestCase):

    def test_str(self):
        address = RPCAddress('test', 'host', 1234)
        assert str(address) == 'test://host:1234'
        assert str(address) == 'test://host:1234'


class TestWebSocketAddress(unittest.TestCase):

    def test_default_values(self):
        address = WebSocketAddress('host', 1234, 'realm')

        assert str(address) == 'wss://host:1234'
        assert isinstance(address.realm, str)
        assert address.realm == 'realm'

        address = WebSocketAddress('host', 1234, 'realm', ssl=False)

        assert str(address) == 'ws://host:1234'


class TestObjectMethodMap(unittest.TestCase):

    class MockObject(object):

        @rpc_utils.expose()
        def method_1(self):
            pass

        @rpc_utils.expose('alias_2')
        def method_2(self):
            pass

    def test_valid_method_map(self):

        obj = self.MockObject()
        expected = {
            'backend.tests.golem.rpc.test_session'
            '.TestObjectMethodMap.MockObject.method_1': obj.method_1,
            'alias_2': obj.method_2,
        }
        result = rpc_utils.object_method_map(obj)

        self.assertEqual(expected, result)


class TestPublisher(TestWithReactor, LogTestCase):

    @defer.inlineCallbacks
    def test_publish(self):
        session = Session(WebSocketAddress('localhost', 12345, 'golem'))
        publisher = Publisher(session)

        session.publish = Mock()
        session.is_closing = Mock()
        session.is_attached = Mock()
        session.is_attached.return_value = True

        # Not connected, session closing
        session.connected = False
        session.is_closing.return_value = True

        with self.assertNoLogs(logger, level='WARNING'):
            yield publisher.publish('alias', 1234, kw='arg')
        assert not session.publish.called

        # Not connected, session not closing
        session.connected = False
        session.is_closing.return_value = False

        with self.assertLogs(logger, level='WARNING'):
            yield publisher.publish('alias', 1234, kw='arg')
        assert not session.publish.called

        # Connected
        session.connected = True
        session.is_closing.return_value = False

        yield publisher.publish('alias', 1234, kw='arg')
        session.publish.assert_called_with('alias', 1234, kw='arg')


def mock_report_calls(func):
    return func


@patch('golem.client.report_calls', mock_report_calls)
class TestClient(unittest.TestCase):

    def setUp(self):
        self.session = Mock()
        self.session.is_attached.return_value = True
        self.session.call.side_effect = lambda *_, **__: defer.Deferred()
        self.session.is_closing = lambda *_: self.session._goodbye_sent or \
            self.session._transport_is_closing

    @patch('golem.rpc.session.ClientProxy._call')
    def test_initialization(self, call_mock, *_):
        rpc_session.ClientProxy(self.session)
        call_mock.assert_called_once_with('sys.exposed_procedures')

    def test_call_no_session(self, *_):
        client = rpc_session.ClientProxy(None)
        with self.assertRaises(RuntimeError):
            client.method_1(arg1=1, arg2='2')

    @patch('golem.rpc.session.ClientProxy._on_error')
    def test_call_not_connected(self, error_mock, *_):
        self.session.connected = False
        self.session._transport_is_closing = False
        self.session._goodbye_sent = False

        client = rpc_session.ClientProxy(self.session)
        client._ready.callback(
            {
                'uri.1': 'golem.client.Client.method_1',
                'uri.2': 'golem.client.Client.method_2',
            },
        )
        deferred = client.method_1(arg1=1, arg2='2')

        self.assertIsInstance(deferred, defer.Deferred)
        self.assertFalse(deferred.called)

        self.session.connected = True

        cbk = Mock()
        client._session._transport_is_closing = True

        deferred = client.method_1(arg1=1, arg2='2')
        deferred.addBoth(cbk)

        cbk.assert_not_called()
        error_mock.assert_not_called()

        cbk = Mock()
        deferred = client.method_1(arg1=1, arg2='2')
        deferred.addBoth(cbk)

        cbk.assert_not_called()
        error_mock.assert_not_called()

        client._session._transport_is_closing = True
        deferred = client.method_1(arg1=1, arg2='2')

        self.assertIsInstance(deferred, defer.Deferred)
        self.assertFalse(deferred.called)

    def test_call_connected(self, *_):
        self.session.connected = True

        client = rpc_session.ClientProxy(self.session)
        client._on_error = Mock()
        deferred = client._call('test', arg1=1, arg2='2')

        self.assertIsInstance(deferred, defer.Deferred)
        self.assertFalse(deferred.called)
        client._on_error.assert_not_called()


class TestSession(unittest.TestCase):

    def test_initialization(self):

        address = WebSocketAddress('host', 1234, 'realm')
        session = Session(address)

        assert isinstance(session.ready, defer.Deferred)
        assert isinstance(session.config, autobahn.wamp.types.ComponentConfig)

        assert session.config.realm == 'realm'
        assert not session.ready.called
