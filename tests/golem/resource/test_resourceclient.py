import time
import unittest
import uuid
from unittest.mock import Mock

import twisted

from golem.core.async import AsyncRequest, async_run
from golem.resource.client import ClientHandler, ClientCommands, ClientError, \
    ClientOptions, ClientConfig
from golem.tools.testwithreactor import TestWithReactor


class MockClientHandler(ClientHandler):
    def __init__(self, commands_class, config):
        super(MockClientHandler, self).__init__(commands_class, config)

    def command_failed(self, exc, cmd, obj_id):
        pass

    def new_client(self):
        return Mock()


class MockClientConfig(ClientConfig):
    def __init__(self, max_concurrent_downloads=3, max_retries=8, timeout=None):
        super(MockClientConfig, self).__init__(max_concurrent_downloads, max_retries, timeout)


class TestClientHandler(unittest.TestCase):

    def test_can_retry(self):
        valid_exceptions = ClientHandler.timeout_exceptions
        config = MockClientConfig()
        handler = MockClientHandler(ClientCommands, config)
        value_exc = valid_exceptions[0]()

        for exc_class in valid_exceptions:
            try:
                exc = exc_class(value_exc)
            except:
                exc = exc_class.__new__(exc_class)

            assert handler._can_retry(exc, ClientCommands.get, str(uuid.uuid4()))
        assert not handler._can_retry(Exception(value_exc), ClientCommands.get, str(uuid.uuid4()))

        obj_id = str(uuid.uuid4())
        exc = valid_exceptions[0]()

        for i in range(0, config.max_retries):
            can_retry = handler._can_retry(exc, ClientCommands.get, obj_id)
            assert can_retry
        assert not handler._can_retry(exc, ClientCommands.get, obj_id)

    def test_exception_type(self):

        valid_exceptions = ClientHandler.timeout_exceptions
        exc = valid_exceptions[0]()
        failure_exc = twisted.python.failure.Failure(exc_value=exc)

        def is_class(object):
            return isinstance(object, type)

        assert is_class(ClientHandler._exception_type(failure_exc))
        assert is_class(ClientHandler._exception_type(exc))


class TestClientOptions(unittest.TestCase):

    def test_init(self):
        with self.assertRaises(AssertionError):
            ClientOptions(None, 1.0)
        with self.assertRaises(AssertionError):
            ClientOptions('client_id', None)

    def test_get(self):
        option = 'test_option'
        options = ClientOptions('valid_id', 1.0, {})
        options.options[option] = True

        with self.assertRaises(ClientError):
            options.get('valid_id', 0.5, option)
        with self.assertRaises(ClientError):
            options.get('invalid_id', 1.0, option)

        assert options.get('valid_id', 1.0, option)

    def test_clone(self):
        dict_options = dict(key='val')
        options = ClientOptions('client_id', 1.0, options=dict_options)
        cloned = options.clone()

        assert isinstance(cloned, ClientOptions)
        assert cloned.options == dict_options
        assert cloned.options is not dict_options

    def test_filtered(self):
        dict_options = dict(key='val')
        options = ClientOptions('client_id', 1.0, options=dict_options)

        filtered = options.filtered('client_id', 1.0)
        assert isinstance(filtered, ClientOptions)
        assert filtered is not options
        assert filtered.client_id == options.client_id
        assert filtered.version == options.version
        assert filtered.options == options.options
        assert filtered.options is not options.options

        filtered = options.filtered(None, 1.0)
        assert filtered is None

        filtered = options.filtered('client_id', None)
        assert isinstance(filtered, ClientOptions)


@unittest.mock.patch('twisted.internet.reactor', create=True)
class TestAsyncRequest(unittest.TestCase):

    def test_initialization(self, reactor):
        AsyncRequest.initialized = False
        request = AsyncRequest(lambda x: x)
        assert AsyncRequest.initialized

        assert request.args == []
        assert request.kwargs == {}
        assert reactor.suggestThreadPoolSize.call_count == 1

        request = AsyncRequest(lambda x: x, "arg", kwarg="kwarg")
        assert request.args == ("arg",)
        assert request.kwargs == {"kwarg": "kwarg"}
        assert reactor.suggestThreadPoolSize.call_count == 1


class TestAsyncRun(TestWithReactor):

    def test_callbacks(self):
        done = [False]

        method = Mock()
        req = AsyncRequest(method)

        def success(*_):
            done[0] = True

        def error(*_):
            done[0] = True

        done[0] = False
        method.called = False
        async_run(req, success, error)
        time.sleep(1)

        assert method.called

        done[0] = False
        method.called = False
        async_run(req)
        time.sleep(1)

        assert method.called
