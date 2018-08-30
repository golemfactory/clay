import uuid
from unittest import TestCase, mock

from twisted.internet.task import Clock

from golem.core.common import each
from golem.market.offer_pool import OfferPool


class TestOfferPool(TestCase):

    def test_add_and_drain(self):
        key = str(uuid.uuid4())
        data = list(range(1, 11))

        OfferPool.add(key, *data)
        assert OfferPool.get(key) == data
        assert OfferPool.contains(key)

        assert OfferPool.drain(key) == data
        assert not OfferPool.contains(key)
        assert not OfferPool.drain(key)

    @mock.patch('twisted.internet.reactor', new_callable=Clock, create=True)
    def test_drain_after(self, clock):
        key = str(uuid.uuid4())
        data = list(range(1, 11))
        result = []

        def callback(r):
            each(result.append, *r)

        OfferPool.add(key, data)
        deferred = OfferPool.drain_after(key, 3.50)
        deferred.addCallback(callback)
        clock.advance(10)

        assert deferred.called
        assert result == data
