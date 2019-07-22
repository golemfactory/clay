from abc import ABC, abstractclassmethod
from typing import Optional, List, Tuple

import golem.ranking.manager.database_manager as dbm


class ProviderStats:
    def __init__(self, usage_benchmark):
        self.usage_benchmark = usage_benchmark


class Offer:
    def __init__(
            self,
            offer_msg,
            task_id: str,
            provider_id: str,
            provider_stats: ProviderStats,
            max_price: float,
            price: float,
            context):
        self.offer_msg = offer_msg
        self.task_id = task_id
        self.provider_id = provider_id
        self.provider_stats = provider_stats
        self.max_price = max_price
        self.price = price
        self.reputation = dbm.get_provider_efficiency(provider_id)
        self.quality = dbm.get_provider_efficacy(provider_id).vector
        self.context = context


class RequestorMarketStrategy(ABC):

    @abstractclassmethod
    def add(cls, offer: Offer):
        """
        Called when a WantToComputeTask arrives.
        """
        pass

    @abstractclassmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        """
        Called when the time to choose offers comes.
        Returns list of offers ordered by preference.
        Returns None for unknonw tasks.
        """
        pass

    @abstractclassmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        """
        Returns number of offers known for the task.
        """
        pass
