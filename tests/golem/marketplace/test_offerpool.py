import sys
from unittest import TestCase
from unittest.mock import Mock, patch, ANY, MagicMock

from golem.marketplace import scale_price, Offer, OfferPool


class TestScalePrice(TestCase):
    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


@patch('golem.ranking.manager.database_manager.get_provider_efficacy')
@patch('golem.ranking.manager.database_manager.get_provider_efficiency')
class TestOfferPool(TestCase):
    def _setup(self, efficacy_mock=None, efficiency_mock=None):
        OfferPool.reset()
        efficacy_mock.return_value = .0

        efficiency_return_value = Mock()
        efficiency_return_value.vector = (.0, .0, .0, .0)
        efficiency_mock.return_value = efficiency_return_value

    @staticmethod
    def _mock_task(task_id=None) -> Mock:
        task = MagicMock()
        task.header.id = task_id if task_id else '1234'
        return task

    def test_resolve_empty_pool(self, *args):
        self._setup(*args)

        task_mock = TestOfferPool._mock_task()
        result = OfferPool.resolve_task_offers(task_mock)
        self.assertIsNone(result)

    def test_empty_after_clear(self, *args):
        self._setup(*args)
        task_mock = TestOfferPool._mock_task()

        OfferPool.add(task_mock, 'provider_1', 1.0)
        self.assertEqual(OfferPool.get_task_offer_count(task_mock), 1)
        OfferPool.clear_offers_for_task(task_mock)
        self.assertEqual(OfferPool.get_task_offer_count(task_mock), 0)

    def test_all_tasks_empty_after_reset(self, *args):
        self._setup(*args)
        task_mock = TestOfferPool._mock_task()

        OfferPool.add(task_mock, 'provider_1', 1.0)
        OfferPool.add(task_mock, 'provider_2', 1.0)
        self.assertEqual(OfferPool.get_task_offer_count(task_mock), 2)
        result = OfferPool.resolve_task_offers(task_mock)
        self.assertEqual(len(result), 2)

    def test_empty_after_resolve(self, *args):
        self._setup(*args)
        task_mock = TestOfferPool._mock_task()

        OfferPool.add(task_mock, 'provider_1', 1.0)
        self.assertEqual(OfferPool.get_task_offer_count(task_mock), 1)
        _ = OfferPool.resolve_task_offers(task_mock)
        self.assertEqual(OfferPool.get_task_offer_count(task_mock), 0)

    def test_resolution_length_correct(self, *args):
        self._setup(*args)
        task_mock = TestOfferPool._mock_task()

        OfferPool.add(task_mock, 'provider_1', 1.0)
        OfferPool.add(task_mock, 'provider_2', 1.0)
        self.assertEqual(OfferPool.get_task_offer_count(task_mock), 2)
        result = OfferPool.resolve_task_offers(task_mock)
        self.assertEqual(len(result), 2)