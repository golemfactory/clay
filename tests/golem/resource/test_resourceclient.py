import time
import unittest

from mock import Mock

from golem.core.async import AsyncRequest, async_run
from golem.resource.client import ClientHandler, ClientError, \
    ClientOptions, ClientConfig
from golem.tools.testwithreactor import TestWithReactor


class MockClientHandler(ClientHandler):
    def __init__(self, config):
        super(MockClientHandler, self).__init__(config)

    def command_failed(self, exc, cmd, obj_id):
        pass

    @staticmethod
    def new_client():
        return Mock()


class MockClientConfig(ClientConfig):
    def __init__(self, max_retries=8, timeout=None):
        super(MockClientConfig, self).__init__(max_retries, timeout)


class TestClientHandler(unittest.TestCase):

    def test_retry(self):
        max_retries = 2
        config = MockClientConfig(max_retries=max_retries)
        handler = MockClientHandler(config)
        valid_exceptions = ClientHandler.retry_exceptions
        value_exc = valid_exceptions[0]()

        for exc_class in valid_exceptions:
            counter = 0
            exc = exc_class(value_exc)

            def func_1():
                nonlocal counter
                counter += 1
                raise exc

            handler._retry(func_1, raise_exc=False)
            assert counter == max_retries

        counter = 0
        with self.assertRaises(ArithmeticError):

            def func_2():
                nonlocal counter
                counter += 1
                raise ArithmeticError

            handler._retry(func_2, raise_exc=False)

        # Exception was raised on first retry
        assert counter == 1


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


class TestAsyncRequest(TestWithReactor):

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
