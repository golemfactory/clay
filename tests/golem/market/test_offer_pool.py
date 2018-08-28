import uuid
from unittest import TestCase, mock

from twisted.internet.task import Clock

from golem.core.common import each
from golem.market.offer_pool import OfferPool


class TestOfferPool(TestCase):

    @mock.patch('twisted.internet.reactor', create=True)
    def test_add_and_drain(self, _):
        pool = OfferPool()
        key = str(uuid.uuid4())
        data = list(range(1, 11))

        pool.add(key, *data)
        assert pool.get(key) == data
        assert key in pool

        assert pool.drain(key) == data
        assert key not in pool
        assert not pool.drain(key)

    @mock.patch('twisted.internet.reactor', new=Clock(), create=True)
    def test_drain_after(self):
        pool = OfferPool()
        key = str(uuid.uuid4())
        data = list(range(1, 11))
        result = []

        def callback(r):
            each(result.append, *r)

        pool.add(key, data)
        deferred = pool.drain_after(key, 3.50)
        deferred.addCallback(callback)

        pool._reactor.advance(10)

        assert deferred.called
        assert result == data
