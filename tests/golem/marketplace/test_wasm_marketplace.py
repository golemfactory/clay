import pdb
from unittest import TestCase
from unittest.mock import Mock

from golem.marketplace import ProviderStats
from golem.marketplace.wasm_marketplace import RequestorWasmMarketStrategy


class TestOfferChoice(TestCase):
    def setUp(self):
        super().setUp()
        mock_offer_1 = Mock()
        mock_offer_1.task_id = 'Task1'
        mock_offer_1.provider_id = 'P1'
        mock_offer_1.quality = (.0, .0, .0, .0)
        mock_offer_1.reputation = .0
        mock_offer_1.price = 5.0
        mock_offer_1.provider_performance = ProviderStats(1.25)
        self.mock_offer_1 = mock_offer_1

        mock_offer_2 = Mock()
        mock_offer_2.task_id = 'Task1'
        mock_offer_2.provider_id = 'P2'
        mock_offer_2.quality = (.0, .0, .0, .0)
        mock_offer_2.reputation = .0
        mock_offer_2.price = 6.0
        mock_offer_2.provider_performance = ProviderStats(0.8)
        self.mock_offer_2 = mock_offer_2

    def test_get_usage_benchmark(self):
        cls = RequestorWasmMarketStrategy
        cls.reset()
        self.assertEqual(cls.get_my_usage_benchmark(), 1.0)
        self.assertEqual(cls.get_usage_factor('P1', 1.0), 1.0)

    def test_resolution_length_correct(self):
        RequestorWasmMarketStrategy.reset()
        self.mock_offer_1.task_id = 'Task1'
        self.mock_offer_2.task_id = 'Task1'
        RequestorWasmMarketStrategy.add(self.mock_offer_1)
        RequestorWasmMarketStrategy.add(self.mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count('Task1'), 2)
        result = RequestorWasmMarketStrategy.resolve_task_offers('Task1')
        self.assertEqual(len(result), 2)

    def test_adjusted_prices(self):
        RequestorWasmMarketStrategy.reset()
        self.mock_offer_1.task_id = 'Task1'
        self.mock_offer_2.task_id = 'Task1'
        RequestorWasmMarketStrategy.add(self.mock_offer_1)
        RequestorWasmMarketStrategy.add(self.mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count('Task1'), 2)
        result = RequestorWasmMarketStrategy.resolve_task_offers('Task1')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].provider_id, 'P2')

    def test_usage_adjustment(self):
        self.mock_offer_1.task_id = 'Task1'
        self.mock_offer_2.task_id = 'Task1'
        RequestorWasmMarketStrategy.reset()
        RequestorWasmMarketStrategy.add(self.mock_offer_1)
        RequestorWasmMarketStrategy.add(self.mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count('Task1'), 2)
        result = RequestorWasmMarketStrategy.resolve_task_offers('Task1')

        RequestorWasmMarketStrategy.report_subtask_usages('Task1',
                                                          [('P1', 5.0), ('P2', 8.0)]
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].provider_id, 'P2')
        self.mock_offer_1.task_id = 'Task2'
        self.mock_offer_2.task_id = 'Task2'
        RequestorWasmMarketStrategy.add(self.mock_offer_1)
        RequestorWasmMarketStrategy.add(self.mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count('Task2'), 2)
        result = RequestorWasmMarketStrategy.resolve_task_offers('Task2')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].provider_id, 'P1')
