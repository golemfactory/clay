import sys
from unittest import TestCase
from unittest.mock import patch, Mock

from golem.marketplace import (RequestorBrassMarketStrategy,
                               ProviderPerformance, Offer)
from golem.marketplace.brass_marketplace import scale_price


def _fake_get_efficacy():

    class A:

        def __init__(self):
            self.vector = (.0, .0, .0, .0)

    return A()


class TestScalePrice(TestCase):

    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


@patch('golem.ranking.manager.database_manager.get_provider_efficiency',
       Mock(return_value=0.0))
@patch('golem.ranking.manager.database_manager.get_provider_efficacy',
       Mock(return_value=_fake_get_efficacy()))
class TestRequestorBrassMarketStrategy(TestCase):
    TASK_A = 'aaa'

    @staticmethod
    def _mock_offer():
        return Offer(
            provider_id='provider_1',
            provider_performance=ProviderPerformance(100),
            max_price=5000,
            price=5000
        )

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
