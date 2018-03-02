import unittest

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.core.deferred import chain_function


class TestChainFunction(unittest.TestCase):

    def test_callback(self):
        deferred = Deferred()
        deferred.callback(True)

        def fn():
            d = Deferred()
            d.callback(True)
            return d

        result = chain_function(deferred, fn)
        assert result.called
        assert result.result
        assert not isinstance(result, Failure)

    def test_main_errback(self):
        deferred = Deferred()
        deferred.errback(Exception())

        def fn():
            d = Deferred()
            d.callback(True)
            return d

        result = chain_function(deferred, fn)
        assert result.called
        assert result.result
        assert isinstance(result.result, Failure)

    def test_fn_errback(self):
        deferred = Deferred()
        deferred.callback(True)

        def fn():
            d = Deferred()
            d.errback(Exception())
            return d

        result = chain_function(deferred, fn)
        assert result.called
        assert result.result
        assert isinstance(result.result, Failure)
