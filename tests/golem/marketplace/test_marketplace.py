import sys
from unittest import TestCase
from unittest.mock import patch, Mock

from golem.marketplace import (
    RequestorBrassMarketStrategy,
    RequestorWasmMarketStrategy,
    ProviderPerformance,
    Offer
)
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
class TestRequestorMarketStrategy(TestCase):
    TASK_A = 'aaa'
    PROVIDER_A = 'provider_a'
    PROVIDER_B = 'provider_b'
    SUBTASK_A = 'subtask_a'
    SUBTASK_B = 'subtask_b'

    def test_brass_payment_computer(self):
        market_strategy = RequestorBrassMarketStrategy
        payment_computer = market_strategy.get_payment_computer(None, None)
        self.assertEqual(payment_computer(1.0), 1.0)

    def test_wasm_payment_computer(self):
        task = Mock()
        task.subtask_price = 10000
        task.header = Mock()
        task.header.subtask_timeout = 10
        market_strategy = RequestorWasmMarketStrategy
        market_strategy.report_subtask_usages(
            self.TASK_A, [(self.PROVIDER_A, self.SUBTASK_A, 5.0),
                          (self.PROVIDER_B, self.SUBTASK_B, 8.0)]
        )
        payment_computer = market_strategy.get_payment_computer(
            task, self.SUBTASK_A
        )
        self.assertEqual(payment_computer(10000), 5000)

        payment_computer = market_strategy.get_payment_computer(
            task, self.SUBTASK_B
        )
        self.assertEqual(payment_computer(10000), 8000)

    def test_wasm_payment_computer_budget_exceeded(self):
        task = Mock()
        task.subtask_price = 6000
        task.header = Mock()
        task.header.subtask_timeout = 10
        market_strategy = RequestorWasmMarketStrategy
        market_strategy.report_subtask_usages(
            self.TASK_A, [(self.PROVIDER_A, self.SUBTASK_A, 5.0),
                          (self.PROVIDER_B, self.SUBTASK_B, 8.0)]
        )
        payment_computer = market_strategy.get_payment_computer(
            task, self.SUBTASK_A
        )
        self.assertEqual(payment_computer(10000), 5000)

        payment_computer = market_strategy.get_payment_computer(
            task, self.SUBTASK_B
        )
        self.assertEqual(payment_computer(10000), 6000)


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
