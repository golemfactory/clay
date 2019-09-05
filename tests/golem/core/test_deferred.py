import asyncio
import unittest
from unittest import mock

from twisted.internet import defer
from twisted.internet.defer import Deferred, succeed, fail
from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.core.common import install_reactor
from golem.core.deferred import (
    chain_function,
    DeferredSeq,
    deferred_from_future
)
from golem.tools.testwithreactor import uninstall_reactor


@mock.patch('golem.core.deferred.deferToThread', lambda x: succeed(x()))
@mock.patch('twisted.internet.reactor', mock.Mock(), create=True)
class TestDeferredSeq(unittest.TestCase):

    def test_init_empty(self):
        assert not DeferredSeq()._seq

    def test_init_with_functions(self):
        def fn_1():
            pass

        def fn_2():
            pass

        assert DeferredSeq().push(fn_1).push(fn_2)._seq == [
            (fn_1, (), {}),
            (fn_2, (), {}),
        ]

    @mock.patch('golem.core.deferred.DeferredSeq._execute')
    def test_execute_empty(self, execute):
        deferred_seq = DeferredSeq()
        with mock.patch('golem.core.deferred.DeferredSeq._execute',
                        wraps=deferred_seq._execute):
            deferred_seq.execute()
        assert execute.called

    def test_execute_functions(self):
        fn_1, fn_2 = mock.Mock(), mock.Mock()

        DeferredSeq().push(fn_1).push(fn_2).execute()
        assert fn_1.called
        assert fn_2.called

    def test_execute_interrupted(self):
        fn_1, fn_2, fn_4 = mock.Mock(), mock.Mock(), mock.Mock()

        def fn_3(*_):
            raise Exception

        def def2t(f, *args, **kwargs) -> Deferred:
            try:
                return succeed(f(*args, **kwargs))
            except Exception as exc:  # pylint: disable=broad-except
                return fail(exc)

        with mock.patch('golem.core.deferred.deferToThread', def2t):
            DeferredSeq().push(fn_1).push(fn_2).push(fn_3).push(fn_4).execute()

        assert fn_1.called
        assert fn_2.called
        assert not fn_4.called


class TestChainFunction(unittest.TestCase):

    def test_callback(self):
        deferred = succeed(True)
        result = chain_function(deferred, lambda: succeed(True))

        assert result.called
        assert result.result
        assert not isinstance(result, Failure)

    def test_main_errback(self):
        deferred = fail(Exception())
        result = chain_function(deferred, lambda: succeed(True))

        assert result.called
        assert result.result
        assert isinstance(result.result, Failure)

    def test_fn_errback(self):
        deferred = succeed(True)
        result = chain_function(deferred, lambda: fail(Exception()))

        assert result.called
        assert result.result
        assert isinstance(result.result, Failure)


class TestDeferredFromFuture(TwistedTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        install_reactor()

    @classmethod
    def tearDownClass(cls) -> None:
        uninstall_reactor()

    @defer.inlineCallbacks
    def test_result(self):
        future = asyncio.Future()
        future.set_result(1)
        deferred = deferred_from_future(future)
        result = yield deferred
        self.assertEqual(result, 1)

    @defer.inlineCallbacks
    def test_exception(self):
        future = asyncio.Future()
        future.set_exception(ValueError())
        deferred = deferred_from_future(future)
        with self.assertRaises(ValueError):
            yield deferred

    @defer.inlineCallbacks
    def test_deferred_cancelled(self):
        future = asyncio.Future()
        deferred = deferred_from_future(future)
        deferred.cancel()
        with self.assertRaises(defer.CancelledError):
            yield deferred

    @defer.inlineCallbacks
    def test_future_cancelled(self):
        future = asyncio.Future()
        deferred = deferred_from_future(future)
        future.cancel()
        with self.assertRaises(defer.CancelledError):
            yield deferred

    @defer.inlineCallbacks
    def test_timed_out(self):
        from twisted.internet import reactor
        coroutine = asyncio.sleep(3)
        future = asyncio.ensure_future(coroutine)
        deferred = deferred_from_future(future)
        deferred.addTimeout(1, reactor)
        with self.assertRaises(defer.TimeoutError):
            yield deferred

    @defer.inlineCallbacks
    def test_deferred_with_timeout_cancelled(self):
        from twisted.internet import reactor
        future = asyncio.Future()
        deferred = deferred_from_future(future)
        deferred.addTimeout(1, reactor)
        deferred.cancel()
        with self.assertRaises(defer.CancelledError):
            yield deferred

    @defer.inlineCallbacks
    def test_future_with_timeout_cancelled(self):
        from twisted.internet import reactor
        future = asyncio.Future()
        deferred = deferred_from_future(future)
        deferred.addTimeout(1, reactor)
        future.cancel()
        with self.assertRaises(defer.CancelledError):
            yield deferred
