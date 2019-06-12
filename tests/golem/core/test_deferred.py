import unittest
from unittest import mock

from twisted.internet.defer import Deferred, succeed, fail
from twisted.python.failure import Failure

from golem.core.deferred import chain_function, DeferredSeq


class TestDeferredSeq(unittest.TestCase):

    def test_init_empty(self):
        assert not DeferredSeq()._seq

    def test_init_with_functions(self):
        fns = [
            lambda _: 7,
            lambda x: x,
        ]
        assert DeferredSeq(*fns)._seq == fns

    @mock.patch('golem.core.deferred.deferToThread', lambda x: succeed(x()))
    def test_execute_empty(self):
        assert DeferredSeq().execute().result

    @mock.patch('golem.core.deferred.deferToThread', lambda x: succeed(x()))
    def test_execute_functions(self):
        fn_1, fn_2 = mock.Mock(), mock.Mock()
        fns = [fn_1, fn_2]
        assert DeferredSeq(*fns).execute().result
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
            DeferredSeq(fn_1, fn_2, fn_3, fn_4).execute()

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
