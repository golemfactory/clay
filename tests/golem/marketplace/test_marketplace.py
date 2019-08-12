import sys
from unittest import TestCase
from unittest.mock import MagicMock

from golem.marketplace import RequestorBrassMarketStrategy, ProviderPerformance
from golem.marketplace.brass_marketplace import scale_price


class TestScalePrice(TestCase):

    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


class TestRequestorBrassMarketStrategy(TestCase):
    TASK_A = 'aaa'

    @staticmethod
    def _mock_offer():
        mock_offer = MagicMock(spec_set=[
            'provider_id',
            'provider_performance',
            'max_price',
            'price',
            'reputation',
            'quality',
        ])
        mock_offer.provider_id = 'provider_1'
        mock_offer.provider_performance = ProviderPerformance(100)
        mock_offer.max_price = 5000
        mock_offer.reputation = 1.0
        mock_offer.quality = (1.0, 1.0, 1.0, 1.0)
        return mock_offer

    def test_choose_from_empty_pool(self):
        offers = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_A)
        self.assertIsNone(offers)

    def test_empty_after_choice(self):
        offer = self._mock_offer()
        RequestorBrassMarketStrategy.add(self.TASK_A, offer)
        RequestorBrassMarketStrategy.add(self.TASK_A, offer)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 2)

        _ = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_A)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 0)

    def test_resolution_length_correct(self):
        offer = self._mock_offer()
        RequestorBrassMarketStrategy.add(self.TASK_A, offer)
        RequestorBrassMarketStrategy.add(self.TASK_A, offer)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 2)
        result = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_A)
        self.assertEqual(len(result), 2)
