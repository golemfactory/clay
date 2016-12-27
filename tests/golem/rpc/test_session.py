import unittest
from collections import OrderedDict

from autobahn.wamp import types
from golem.rpc.session import RPCAddress, WebSocketAddress, object_method_map, Publisher, Client, Session
from mock import Mock
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure


class TestRPCAddress(unittest.TestCase):

    def test_str(self):
        address = RPCAddress('test', 'host', 1234)
        assert str(address) == 'test://host:1234'
        assert unicode(address) == u'test://host:1234'


class TestWebSocketAddress(unittest.TestCase):

    def test_default_values(self):
        address = WebSocketAddress('host', 1234, 'realm', ssl=True)

        assert unicode(address) == u'wss://host:1234'
        assert isinstance(address.realm, unicode)
        assert address.realm == u'realm'

        address = WebSocketAddress('host', 1234, 'realm')

        assert unicode(address) == u'ws://host:1234'


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


class TestPublisher(unittest.TestCase):

    def test_publish(self):

        session = Mock()
        publisher = Publisher(session)

        session.connected = False
        publisher.publish('alias', 1234, kw='arg')
        assert not session.publish.called

        session.connected = True
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
        self.method_map = dict(
            method_1='alias_1',
            method_2='alias_2'
        )

    def test_initialization(self):
        client = Client(self.session, self.method_map)
        assert hasattr(client, 'method_1')
        assert hasattr(client, 'method_2')
        assert callable(getattr(client, 'method_1'))
        assert callable(getattr(client, 'method_2'))

    def test_call_no_session(self):

        client = Client(None, self.method_map)
        with self.assertRaises(AttributeError):
            client.method_1(arg1=1, arg2='2')

    def test_call_not_connected(self):

        result = self.Result()
        self.session.connected = False

        client = Client(self.session, self.method_map)
        client._on_error = Mock()
        deferred = client.method_1(arg1=1, arg2='2')

        assert isinstance(deferred, Deferred)
        assert deferred.called

        deferred.addCallbacks(result.set, result.set)
        assert isinstance(result.value, Failure)
        assert not client._on_error.called

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
        assert isinstance(session.config, types.ComponentConfig)

        assert session.config.realm == u'realm'
        assert not session.ready.called
