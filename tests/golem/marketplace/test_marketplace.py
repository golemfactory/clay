import sys
from unittest import TestCase
from unittest import mock

from golem.marketplace.marketplace import Offer, ProviderPerformance
from golem.marketplace.brass_marketplace import (
    scale_price,
    RequestorBrassMarketStrategy
)


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


@mock.patch('golem.ranking.manager.database_manager.get_provider_efficiency',
            mock.Mock(return_value=0.0))
@mock.patch('golem.ranking.manager.database_manager.get_provider_efficacy',
            mock.Mock(return_value=_fake_get_efficacy()))
class TestRequestorBrassMarketStrategy(TestCase):
    TASK_A = 'a'
    TASK_B = 'b'

    @staticmethod
    def _mock_offer() -> Offer:
        return Offer(
            'provider_1',
            ProviderPerformance(0.1),
            1234,
            123
        )

    def test_resolve_empty_pool(self):
        RequestorBrassMarketStrategy.reset()

        result = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_A)
        self.assertIsNone(result)

    def test_empty_after_clear(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer = self._mock_offer()
        RequestorBrassMarketStrategy.add(self.TASK_A, mock_offer)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 1)
        RequestorBrassMarketStrategy.clear_offers_for_task(self.TASK_A)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 0)

    def test_all_tasks_empty_after_reset(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer_1 = self._mock_offer()
        mock_offer_2 = self._mock_offer()

        RequestorBrassMarketStrategy.add(self.TASK_A, mock_offer_1)
        RequestorBrassMarketStrategy.add(self.TASK_B, mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 1)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_B), 1)

        RequestorBrassMarketStrategy.reset()

        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 0)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_B), 0)

    def test_empty_after_resolve(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer_1 = self._mock_offer()
        mock_offer_2 = self._mock_offer()

        RequestorBrassMarketStrategy.add(self.TASK_A, mock_offer_1)
        RequestorBrassMarketStrategy.add(self.TASK_A, mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 2)

        _ = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_A)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A),
            0
        )

    def test_resolution_length_correct(self):
        RequestorBrassMarketStrategy.reset()

        mock_offer_1 = self._mock_offer()
        mock_offer_2 = self._mock_offer()

        RequestorBrassMarketStrategy.add(self.TASK_A, mock_offer_1)
        RequestorBrassMarketStrategy.add(self.TASK_A, mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_A), 2)
        result = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_A)
        self.assertEqual(len(result), 2)

        RequestorBrassMarketStrategy.add(self.TASK_B, mock_offer_1)
        RequestorBrassMarketStrategy.add(self.TASK_B, mock_offer_2)
        self.assertEqual(
            RequestorBrassMarketStrategy.get_task_offer_count(self.TASK_B), 2)
        result = RequestorBrassMarketStrategy.resolve_task_offers(self.TASK_B)
        self.assertEqual(len(result), 2)
