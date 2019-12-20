import sys
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from ethereum.utils import denoms

from golem_messages.factories.tasks import ReportComputedTaskFactory
from golem_messages.datastructures.stats import ProviderStats

from golem import testutils

from golem.marketplace import (
    RequestorBrassMarketStrategy,
    RequestorWasmMarketStrategy,
    ProviderBrassMarketStrategy,
    ProviderWasmMarketStrategy,
    ProviderPerformance,
)
from golem.marketplace.brass_marketplace import scale_price

PWEI = denoms.finney
HOUR = 3600
NANOSECOND = 1e-9


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
class TestMarketStrategy(testutils.DatabaseFixture):
    TASK_A = 'aaa'
    PROVIDER_A = 'provider_a'
    PROVIDER_B = 'provider_b'
    SUBTASK_A = 'subtask_a'
    SUBTASK_B = 'subtask_b'
    BUDGET = 200 * PWEI

    def test_brass_calculate_payment(self):
        rct = ReportComputedTaskFactory(**{
            'task_to_compute__want_to_compute_task__price': 100,
            'task_to_compute__want_to_compute_task'
            '__task_header__subtask_timeout': 360,
        })
        # payment = price * timeout / 3600
        self.assertEqual(
            RequestorBrassMarketStrategy.calculate_payment(rct), 10)
        self.assertEqual(
            ProviderBrassMarketStrategy.calculate_payment(rct), 10)

    def _usage_rct_factory(self, usage):
        return ReportComputedTaskFactory(**{
            'task_to_compute__want_to_compute_task__price': 100 * PWEI,
            'task_to_compute__want_to_compute_task'
            '__task_header__subtask_budget': self.BUDGET,
            'stats': ProviderStats(**{
                'cpu_stats': {
                    'cpu_usage': {
                        'total_usage': usage / NANOSECOND
                    }
                }
            })
        })

    def test_wasm_calculate_payment(self):
        rct = self._usage_rct_factory(0.5 * HOUR)
        expected = 50 * PWEI
        self.assertEqual(
            RequestorWasmMarketStrategy.calculate_payment(rct),
            expected
        )
        self.assertEqual(
            ProviderWasmMarketStrategy.calculate_payment(rct),
            50 * PWEI
        )

    def test_wasm_calculate_payment_budget_exceeded(self):
        rct = self._usage_rct_factory(3.0 * HOUR)
        # clamp at max payment -> max_price * subtask_timeout / 3600
        expected = self.BUDGET
        self.assertEqual(
            RequestorWasmMarketStrategy.calculate_payment(rct),
            expected
        )
        self.assertEqual(
            ProviderWasmMarketStrategy.calculate_payment(rct),
            expected
        )


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
        self.assertEqual(offers, [])

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
