from unittest.mock import Mock

from golem import testutils

from golem.marketplace import ProviderPerformance
from golem.marketplace.wasm_marketplace import RequestorWasmMarketStrategy


USAGE_SECOND = 1e9  # usage is measured in nanoseconds


class TestOfferChoice(testutils.DatabaseFixture):
    TASK_1 = 'task_1'
    TASK_2 = 'task_2'
    PROVIDER_1 = 'P1'
    PROVIDER_2 = 'P2'
    SUBTASK_1 = 'subtask_1'
    SUBTASK_2 = 'subtask_2'

    def setUp(self):
        super().setUp()
        RequestorWasmMarketStrategy.reset()
        mock_offer_1 = Mock()
        mock_offer_1.provider_id = self.PROVIDER_1
        mock_offer_1.quality = (.0, .0, .0, .0)
        mock_offer_1.reputation = .0
        mock_offer_1.price = 5.0
        mock_offer_1.provider_performance = ProviderPerformance(
            1.25 * USAGE_SECOND)
        self.mock_offer_1 = mock_offer_1

        mock_offer_2 = Mock()
        mock_offer_2.provider_id = self.PROVIDER_2
        mock_offer_2.quality = (.0, .0, .0, .0)
        mock_offer_2.reputation = .0
        mock_offer_2.price = 6.0
        mock_offer_2.provider_performance = ProviderPerformance(
            0.8 * USAGE_SECOND)
        self.mock_offer_2 = mock_offer_2

    def test_get_usage_benchmark(self):
        self.assertEqual(
            RequestorWasmMarketStrategy.get_my_usage_benchmark(),
            RequestorWasmMarketStrategy.DEFAULT_USAGE_BENCHMARK
        )
        self.assertEqual(
            RequestorWasmMarketStrategy.get_usage_factor(
                self.PROVIDER_1,
                RequestorWasmMarketStrategy.DEFAULT_USAGE_BENCHMARK
            ),
            1.0
        )

    def _resolve_task_offers(self):
        RequestorWasmMarketStrategy.add(self.TASK_1, self.mock_offer_1)
        RequestorWasmMarketStrategy.add(self.TASK_1, self.mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count(self.TASK_1), 2)
        return RequestorWasmMarketStrategy.resolve_task_offers(self.TASK_1)

    def test_resolution_length_correct(self):
        result = self._resolve_task_offers()
        self.assertEqual(len(result), 2)

    def test_adjusted_prices(self):
        result = self._resolve_task_offers()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].provider_id, self.PROVIDER_2)

    def test_usage_adjustment(self):
        result = self._resolve_task_offers()
        self.assertEqual(
            RequestorWasmMarketStrategy.get_usage_factor(self.PROVIDER_1, -1),
            1.25
        )
        self.assertEqual(
            RequestorWasmMarketStrategy.get_usage_factor(self.PROVIDER_2, -1),
            0.8
        )
        RequestorWasmMarketStrategy.report_subtask_usages(
            self.TASK_1, [(self.PROVIDER_1, self.SUBTASK_1, 5.0),
                          (self.PROVIDER_2, self.SUBTASK_2, 8.0)]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].provider_id, self.PROVIDER_2)
        RequestorWasmMarketStrategy.add(self.TASK_2, self.mock_offer_1)
        RequestorWasmMarketStrategy.add(self.TASK_2, self.mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count(self.TASK_2), 2)
        result = RequestorWasmMarketStrategy.resolve_task_offers(self.TASK_2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].provider_id, self.PROVIDER_1)

        self.assertGreater(
            RequestorWasmMarketStrategy.get_usage_factor(self.PROVIDER_2, -1),
            RequestorWasmMarketStrategy.get_usage_factor(self.PROVIDER_1, -1),
        )
