from unittest import TestCase, mock

from freezegun import freeze_time

from golem.network.transport.limiter import CallRateLimiter


@mock.patch('twisted.internet.reactor', create=True)
class TestCallRateLimiter(TestCase):

    @freeze_time("2018-01-01 00:00:00")
    def test_call(self, reactor):
        limiter = CallRateLimiter()
        fn = mock.Mock(return_value=True)

        for _ in range(5):
            limiter.call(fn)
        assert not reactor.callLater.called

    @freeze_time("2018-01-01 00:00:00")
    def test_delay(self, reactor):
        limiter = CallRateLimiter()
        fn = mock.Mock(return_value=True)
        n = int(limiter._limiter._capacity * 1.5)

        for _ in range(n):
            limiter.call(fn)
        assert reactor.callLater.called
