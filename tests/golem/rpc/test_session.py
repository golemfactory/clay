import unittest
from collections import OrderedDict

import autobahn
from mock import Mock
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.rpc.session import (
    RPCAddress, WebSocketAddress, Publisher, Client, Session,
    object_method_map, logger
)
from golem.tools.assertlogs import LogTestCase
import collections


class TestRPCAddress(unittest.TestCase):

    def test_str(self):
        address = RPCAddress('test', 'host', 1234)
        assert str(address) == 'test://host:1234'
        assert str(address) == 'test://host:1234'


class TestWebSocketAddress(unittest.TestCase):

    def test_default_values(self):
        address = WebSocketAddress('host', 1234, 'realm', ssl=True)

        assert str(address) == 'wss://host:1234'
        assert isinstance(address.realm, str)
        assert address.realm == 'realm'

        address = WebSocketAddress('host', 1234, 'realm')

        assert str(address) == 'ws://host:1234'


class TestObjectMethodMap(unittest.TestCase):

    class MockObject(object):

        def method_1(self):
            pass

        def method_2(self):
            pass

    def test_valid_method_map(self):

        obj = self.MockObject()
        valid_method_map = OrderedDict([
            ('method_1', 'alias_1'),
            ('method_2', 'alias_2')
        ])
        expected_output = [
            (obj.method_1, 'alias_1'),
            (obj.method_2, 'alias_2')
        ]

        assert object_method_map(obj, valid_method_map) == expected_output

    def test_invalid_method_map(self):

        obj = self.MockObject()
        invalid_method_map = OrderedDict([
            ('method_1', 'alias_1'),
            ('method_x', 'alias_x')
        ])

        with self.assertRaises(AttributeError):
            object_method_map(obj, invalid_method_map)


class TestPublisher(LogTestCase):

    def test_publish(self):

        session = Mock()
        publisher = Publisher(session)

        # Not connected, session closing
        session.connected = False
        session.is_closing.return_value = True

        with self.assertNoLogs(logger, level='WARNING'):
            publisher.publish('alias', 1234, kw='arg')
        assert not session.publish.called

        # Not connected, session not closing
        session.connected = False
        session.is_closing.return_value = False

        with self.assertLogs(logger, level='WARNING'):
            publisher.publish('alias', 1234, kw='arg')
        assert not session.publish.called

        # Connected
        session.connected = True
        session.is_closing.return_value = False

        publisher.publish('alias', 1234, kw='arg')
        session.publish.assert_called_with('alias', 1234, kw='arg')


class TestClient(unittest.TestCase):

    class Result(object):
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    def setUp(self):
        self.session = Mock()
        self.session.call.return_value = Deferred()
        self.session.is_closing = lambda *_: self.session._goodbye_sent or \
                                             self.session._transport_is_closing
        self.method_map = dict(
            method_1='alias_1',
            method_2='alias_2'
        )

    def test_initialization(self):
        client = Client(self.session, self.method_map)
        assert hasattr(client, 'method_1')
        assert hasattr(client, 'method_2')
        assert isinstance(getattr(client, 'method_1'), collections.Callable)
        assert isinstance(getattr(client, 'method_2'), collections.Callable)

    def test_call_no_session(self):

        client = Client(None, self.method_map)
        with self.assertRaises(AttributeError):
            client.method_1(arg1=1, arg2='2')

    def test_call_not_connected(self):

        self.session.connected = False
        self.session._transport_is_closing = False
        self.session._goodbye_sent = False

        client = Client(self.session, self.method_map)
        client._on_error = Mock()
        deferred = client.method_1(arg1=1, arg2='2')

        assert isinstance(deferred, Deferred)
        assert deferred.called

        result = self.Result()
        client._session._transport_is_closing = False

        deferred = client.method_1(arg1=1, arg2='2')
        deferred.addBoth(result.set)

        assert isinstance(result.value, Failure)
        assert not client._on_error.called

        client._session._transport_is_closing = True
        deferred = client.method_1(arg1=1, arg2='2')

        assert isinstance(deferred, Deferred)
        assert not deferred.called

    def test_call_connected(self):

        self.session.connected = True

        client = Client(self.session, self.method_map)
        client._on_error = Mock()
        deferred = client.method_1(arg1=1, arg2='2')

        assert isinstance(deferred, Deferred)
        assert not deferred.called
        assert not client._on_error.called


class TestSession(unittest.TestCase):

    def test_initialization(self):

        address = WebSocketAddress('host', 1234, 'realm')
        session = Session(address)

        assert isinstance(session.ready, Deferred)
        assert isinstance(session.config, autobahn.wamp.types.ComponentConfig)

        assert session.config.realm == 'realm'
        assert not session.ready.called
