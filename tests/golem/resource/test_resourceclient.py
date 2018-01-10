import time

from unittest import TestCase
from unittest.mock import Mock

from golem.core.async import AsyncRequest, async_run
from golem.resource.client import ClientHandler, ClientError, \
    ClientOptions, ClientConfig
from golem.tools.testwithreactor import TestWithReactor


class TestClientHandler(TestCase):

    def setUp(self):
        config = ClientConfig(max_retries=3)
        self.handler = ClientHandler(config)

    def test_retry(self):
        valid_exceptions = ClientHandler.retry_exceptions
        value_exc = valid_exceptions[0]()
        counter = 0

        def func(e):
            nonlocal counter
            counter += 1
            raise e

        for exc_class in valid_exceptions:
            counter = 0
            self.handler._retry(func, exc_class(value_exc), raise_exc=False)

            # All retries spent
            assert counter == self.handler.config.max_retries

    def test_retry_unsupported_exception(self):
        counter = 0

        with self.assertRaises(ArithmeticError):

            def func():
                nonlocal counter
                counter += 1
                raise ArithmeticError

            self.handler._retry(func, raise_exc=False)

        # Exception was raised on first retry
        assert counter == 1


class TestClientOptions(TestCase):

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
        method = Mock()
        request = AsyncRequest(method)
        result = Mock(value=None)

        def success(*_):
            result.value = True

        def error(*_):
            result.value = False

        async_run(request)
        time.sleep(0.5)

        assert method.call_count == 1
        assert result.value is None

        async_run(request, success)
        time.sleep(0.5)

        assert method.call_count == 2
        assert result.value is True

        method.side_effect = Exception
        async_run(request, success, error)
        time.sleep(0.5)

        assert method.call_count == 3
        assert result.value is False
