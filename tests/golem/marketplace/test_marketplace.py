import sys
from unittest import TestCase
from unittest.mock import Mock

from golem.marketplace import scale_price, RequestorBrassMarketStrategy


class TestScalePrice(TestCase):
    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


class TestRequestorBrassMarketStrategy(TestCase):
    def test_resolve_empty_pool(self):
        RequestorBrassMarketStrategy.reset()

        result = RequestorBrassMarketStrategy.resolve_task_offers('task_id')
        self.assertIsNone(result)

    def test_empty_after_clear(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer = Mock()
        mock_offer.task_id = 'aaa'
        RequestorBrassMarketStrategy.add(mock_offer)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'), 1)
        RequestorBrassMarketStrategy.clear_offers_for_task('aaa')
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'), 0)

    def test_all_tasks_empty_after_reset(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer_1 = Mock()
        mock_offer_1.task_id = 'aaa'

        mock_offer_2 = Mock()
        mock_offer_2.task_id = 'bbb'

        RequestorBrassMarketStrategy.add(mock_offer_1)
        RequestorBrassMarketStrategy.add(mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'), 1)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('bbb'), 1)

        RequestorBrassMarketStrategy.reset()

        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'), 0)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('bbb'), 0)

    def test_empty_after_resolve(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer_1 = Mock()
        mock_offer_1.task_id = 'aaa'
        mock_offer_1.quality = (.0, .0, .0, .0)
        mock_offer_1.reputation = .0
        mock_offer_1.price = .0

        mock_offer_2 = Mock()
        mock_offer_2.task_id = 'aaa'
        mock_offer_2.quality = (.0, .0, .0, .0)
        mock_offer_2.reputation = .0
        mock_offer_2.price = .0

        RequestorBrassMarketStrategy.add(mock_offer_1)
        RequestorBrassMarketStrategy.add(mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'), 2)

        _ = RequestorBrassMarketStrategy.resolve_task_offers('aaa')
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'),
            0
        )

    def test_resolution_length_correct(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer_1 = Mock()
        mock_offer_1.task_id = 'aaa'
        mock_offer_1.quality = (.0, .0, .0, .0)
        mock_offer_1.reputation = .0
        mock_offer_1.price = .0

        mock_offer_2 = Mock()
        mock_offer_2.task_id = 'aaa'
        mock_offer_2.quality = (.0, .0, .0, .0)
        mock_offer_2.reputation = .0
        mock_offer_2.price = .0

        RequestorBrassMarketStrategy.add(mock_offer_1)
        RequestorBrassMarketStrategy.add(mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count('aaa'), 2)
        result = RequestorBrassMarketStrategy.resolve_task_offers('aaa')
        self.assertEqual(len(result), 2)
