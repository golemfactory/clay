import pdb
from unittest import TestCase
from unittest.mock import Mock

from golem.marketplace import ProviderStats
from golem.marketplace.wasm_marketplace import RequestorWasmMarketStrategy

class TestOfferChoice(TestCase):

    def test_get_usage_benchmark(self):
        cls = RequestorWasmMarketStrategy
        cls.reset()
        self.assertEqual(cls.get_my_usage_benchmark(), 1.0)
        self.assertEqual(cls.get_usage_factor('P1', 1.0), 1.0)

    def test_resolution_length_correct(self):
        RequestorWasmMarketStrategy.reset()

        mock_offer_1 = Mock()
        mock_offer_1.task_id = 'Task1'
        mock_offer_1.provider_id = 'P1'
        mock_offer_1.quality = (.0, .0, .0, .0)
        mock_offer_1.reputation = .0
        mock_offer_1.price = .0
        mock_offer_1.provider_stats = ProviderStats(1.0)

        mock_offer_2 = Mock()
        mock_offer_2.task_id = 'aaa'
        mock_offer_2.provider_id = 'P1'
        mock_offer_2.quality = (.0, .0, .0, .0)
        mock_offer_2.reputation = .0
        mock_offer_2.price = .0
        mock_offer_2.provider_stats = ProviderStats(1.0)

        RequestorWasmMarketStrategy.add(mock_offer_1)
        RequestorWasmMarketStrategy.add(mock_offer_2)
        self.assertEqual(
            RequestorWasmMarketStrategy.get_task_offer_count('aaa'), 2)
        result = RequestorWasmMarketStrategy.resolve_task_offers('aaa')
        self.assertEqual(len(result), 2)
