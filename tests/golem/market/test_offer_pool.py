import uuid
from unittest import TestCase, mock

from freezegun import freeze_time
from twisted.internet.task import Clock

from golem.core.common import each
from golem.market.offer_pool import OfferPool


class TestOfferPool(TestCase):

    def test_peek(self):
        key = str(uuid.uuid4())
        data = list(range(1, 11))

        OfferPool.add(key, *data)

        assert OfferPool.peek(key) == data
        assert OfferPool.peek(key, 0) == data
        assert OfferPool.peek(key, 1000) == data
        assert OfferPool.peek(key, -1) == []
        assert OfferPool.peek(key, 1) == data[:1]
        assert OfferPool.peek(key, 5) == data[:5]

    def test_add_and_drain(self):
        key = str(uuid.uuid4())
        data = list(range(1, 11))

        OfferPool.add(key, *data)
        assert OfferPool.peek(key) == data
        assert OfferPool.contains(key)

        assert OfferPool.drain(key) == data
        assert not OfferPool.contains(key)
        assert not OfferPool.drain(key)

    @mock.patch('twisted.internet.reactor', new_callable=Clock, create=True)
    def test_drain_after(self, clock):
        key = str(uuid.uuid4())
        data = list(range(1, 11))
        result = []

        OfferPool.add(key, *data)
        deferred = OfferPool.drain_after(key, 3.50)
        deferred.addCallback(lambda r: each(result.append, r))
        deferred.addErrback(self.fail)

        clock.advance(10)

        assert deferred.called
        assert result == data

    @mock.patch('twisted.internet.reactor', new_callable=Clock, create=True)
    def test_take(self, clock):
        key = str(uuid.uuid4())
        data = list(range(1, 11))

        count = 3
        result = []

        deferred = OfferPool.take_when(key, count, 60.0)
        deferred.addCallback(lambda r: each(result.append, r))
        deferred.addErrback(self.fail)

        clock.advance(1)
        assert not result

        OfferPool.add(key, data[0])
        clock.advance(1)
        assert not result

        OfferPool.add(key, data[1])
        clock.advance(1)
        assert not result

        OfferPool.add(key, data[2])
        clock.advance(1)
        assert deferred.called
        assert result == data[:count]

    @freeze_time("2020-01-01 00:00:00")
    @mock.patch('twisted.internet.reactor', new_callable=Clock, create=True)
    def test_take_timeout(self, clock):
        key = str(uuid.uuid4())
        result = []

        deferred = OfferPool.take_when(key, 10, 5.0)
        deferred.addCallback(self.fail)
        deferred.addErrback(lambda _: result.append(True))

        with freeze_time("2020-01-01 00:01:00"):
            clock.advance(10)

        assert result
        assert result[0] is True
