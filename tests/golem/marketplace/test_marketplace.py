import sys
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from ethereum.utils import denoms

from golem import testutils

from golem.marketplace import (
    RequestorBrassMarketStrategy,
    RequestorWasmMarketStrategy,
    ProviderPerformance,
)
from golem.marketplace.brass_marketplace import scale_price

GWEI = denoms.szabo
HOUR = 3600


def _fake_get_efficacy():
    return Mock(vector=(.0, .0, .0, .0))


class TestScalePrice(TestCase):

    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


@patch('golem.ranking.manager.database_manager.get_provider_efficiency',
       Mock(return_value=0.0))
@patch('golem.ranking.manager.database_manager.get_provider_efficacy',
       Mock(return_value=_fake_get_efficacy()))
class TestRequestorMarketStrategy(testutils.DatabaseFixture):
    TASK_A = 'aaa'
    PROVIDER_A = 'provider_a'
    PROVIDER_B = 'provider_b'
    SUBTASK_A = 'subtask_a'
    SUBTASK_B = 'subtask_b'

    def test_brass_payment_computer(self):
        market_strategy = RequestorBrassMarketStrategy
        task = Mock()
        task.header = Mock()
        task.header.subtask_timeout = 360
        payment_computer = market_strategy.get_payment_computer(
            None,
            task.header.subtask_timeout,
            task.subtask_price)
        self.assertEqual(payment_computer(100), 10)  # price * timeout / 3600

    def test_wasm_payment_computer(self):
        task = Mock()
        task.subtask_price = 6000 * GWEI
        task.header = Mock()
        task.header.subtask_timeout = 10
        market_strategy = RequestorWasmMarketStrategy
        market_strategy.report_subtask_usages(
            self.TASK_A, [(self.PROVIDER_A, self.SUBTASK_A, 5.0 * HOUR),
                          (self.PROVIDER_B, self.SUBTASK_B, 8.0 * HOUR)]
        )
        payment_computer = market_strategy.get_payment_computer(
            self.SUBTASK_A,
            task.header.subtask_timeout,
            task.subtask_price)
        self.assertEqual(payment_computer(1000 * GWEI), 5000 * GWEI)

        payment_computer = market_strategy.get_payment_computer(
            self.SUBTASK_B,
            task.header.subtask_timeout,
            task.subtask_price)
        self.assertEqual(payment_computer(1000 * GWEI), 6000 * GWEI)

    def test_wasm_payment_computer_budget_exceeded(self):
        task = Mock()
        task.subtask_price = 6000 * GWEI
        task.header = Mock()
        task.header.subtask_timeout = 10
        market_strategy = RequestorWasmMarketStrategy
        market_strategy.report_subtask_usages(
            self.TASK_A, [(self.PROVIDER_A, self.SUBTASK_A, 5.0 * HOUR),
                          (self.PROVIDER_B, self.SUBTASK_B, 8.0 * HOUR)]
        )
        payment_computer = market_strategy.get_payment_computer(
            self.SUBTASK_A,
            task.header.subtask_timeout,
            task.subtask_price)
        self.assertEqual(payment_computer(1000 * GWEI), 5000 * GWEI)

        payment_computer = market_strategy.get_payment_computer(
            self.SUBTASK_B,
            task.header.subtask_timeout,
            task.subtask_price)
        self.assertEqual(payment_computer(1000 * GWEI), 6000 * GWEI)


@patch('golem.ranking.manager.database_manager.get_provider_efficiency',
       Mock(return_value=0.0))
@patch('golem.ranking.manager.database_manager.get_provider_efficacy',
       Mock(return_value=_fake_get_efficacy()))
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
