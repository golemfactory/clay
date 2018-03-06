from unittest import TestCase, mock

from freezegun import freeze_time
from token_bucket import MemoryStorage

from golem.network.transport.limiter import CallRateLimiter


@mock.patch('twisted.internet.reactor', create=True)
class TestCallRateLimiter(TestCase):

    def test_init(self, _):
        rate = 10
        capacity_factor = 2.
        delay_factor = 3.

        limiter = CallRateLimiter(rate=rate,
                                  capacity_factor=capacity_factor,
                                  delay_factor=delay_factor)

        assert limiter.delay_factor == delay_factor
        assert limiter._limiter._capacity == int(rate * capacity_factor)
        assert isinstance(limiter._limiter._storage, MemoryStorage)

    @freeze_time("2018-01-01 00:00:00")
    def test_call(self, reactor):
        limiter = CallRateLimiter()
        fn = mock.Mock(return_value=True)
        # Call count is equal to current rate
        # and less than capacity (defaults)
        n = limiter._limiter._rate

        for _ in range(n):
            limiter.call(fn)
        assert not reactor.callLater.called

    @freeze_time("2018-01-01 00:00:00")
    def test_delay(self, reactor):
        limiter = CallRateLimiter()
        fn = mock.Mock(return_value=True)
        # Call count exceeds the current capacity
        n = int(limiter._limiter._capacity * 1.5)

        for _ in range(n):
            limiter.call(fn)
        assert reactor.callLater.called
