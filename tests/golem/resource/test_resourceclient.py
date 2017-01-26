import types
import unittest
import uuid

import time
import twisted
from golem.tools.testwithreactor import TestWithReactor
from mock import Mock, patch
from twisted.internet.defer import Deferred

from golem.resource.client import ClientHandler, ClientCommands, ClientError, ClientOptions, ClientConfig, AsyncRequest, \
    async_run


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

        def init(instance, exc, *args, **kwargs):
            instance.value = exc
            instance.exc_value = exc
            exc.frames = ['frame']

        for exc_class in valid_exceptions:
            org_init = exc_class.__init__
            exc_class.__init__ = init

            try:
                exc = exc_class(value_exc)
            except:
                exc = None

            exc_class.__init__ = org_init

            assert handler._can_retry(exc, ClientCommands.get, str(uuid.uuid4()))
        assert not handler._can_retry(Exception(value_exc), ClientCommands.get, str(uuid.uuid4()))

        obj_id = str(uuid.uuid4())
        exc = valid_exceptions[0]()

        for i in xrange(0, config.max_retries):
            can_retry = handler._can_retry(exc, ClientCommands.get, obj_id)
            assert can_retry
        assert not handler._can_retry(exc, ClientCommands.get, obj_id)

    def test_exception_type(self):

        valid_exceptions = ClientHandler.timeout_exceptions
        exc = valid_exceptions[0]()
        failure_exc = twisted.python.failure.Failure(exc_value=exc)

        def is_class(object):
            return isinstance(object, (type, types.ClassType))

        assert is_class(ClientHandler._exception_type(failure_exc))
        assert is_class(ClientHandler._exception_type(exc))


class TestClientOptions(unittest.TestCase):

    def test_get(self):
        option = 'test_option'

        options = ClientOptions('valid_id', 'valid_version', {})
        options.options[option] = True

        with self.assertRaises(ClientError):
            options.get('valid_id', 'invalid_version', option)
        with self.assertRaises(ClientError):
            options.get('invalid_id', 'valid_version', option)

        assert options.get('valid_id', 'valid_version', option)


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
