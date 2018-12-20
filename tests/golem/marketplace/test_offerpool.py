from unittest import TestCase
from unittest.mock import Mock, patch, ANY

from golem.marketplace import Offer, OfferPool


@patch('golem.marketplace.offerpool.task.deferLater')
class TestOfferPool(TestCase):
    @staticmethod
    def _mock_offer() -> Offer:
        return Offer(
            scaled_price=1.,
            reputation=1.,
            quality=(0., 0., 0., 0.),
        )

    def test_callback(self, defer_later):
        task_id = 'test_task_id'
        deferreds = []
        for _ in range(3):
            deferred = OfferPool.add(task_id, self._mock_offer())
            deferreds.append(deferred)

        defer_later.assert_called_once_with(
            ANY,
            OfferPool._INTERVAL,
            ANY,
            ANY,
        )

        defer_later.call_args[0][2](*defer_later.call_args[0][3:])
        for deferred in deferreds:
            assert deferred.called

    def test_different_tasks(self, defer_later):
        task_id1 = 'test_task_id1'
        task_id2 = 'test_task_id2'

        OfferPool.add(task_id1, Mock())
        defer_later.assert_called_once_with(ANY, ANY, ANY, task_id1)
        defer_later.reset_mock()

        OfferPool.add(task_id2, Mock())
        defer_later.assert_called_once_with(ANY, ANY, ANY, task_id2)
        defer_later.reset_mock()

    def test_defer_once_per_batch(self, defer_later):
        task_id = 'test_task_id'

        OfferPool.add(task_id, self._mock_offer())
        defer_later.assert_called_once_with(ANY, ANY, ANY, task_id)

        OfferPool.add(task_id, self._mock_offer())
        defer_later.assert_called_once()

        defer_later.call_args[0][2](*defer_later.call_args[0][3:])
        defer_later.reset_mock()

        OfferPool.add(task_id, self._mock_offer())
        defer_later.assert_called_once_with(ANY, ANY, ANY, task_id)
