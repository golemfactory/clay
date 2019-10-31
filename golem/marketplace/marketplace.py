from abc import ABC, abstractclassmethod
from typing import Optional, List

from dataclasses import dataclass


class ProviderPerformance:
    def __init__(self, usage_benchmark):
        self.usage_benchmark = usage_benchmark


@dataclass
class Offer:
    provider_id: str
    provider_performance: ProviderPerformance
    max_price: float
    price: float


class RequestorMarketStrategy(ABC):

    @abstractclassmethod
    def add(cls, task_id: str, offer: Offer):
        """
        Called when a WantToComputeTask arrives.
        """
        raise NotImplementedError()

    # pylint: disable-msg=line-too-long
    @abstractclassmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        """
        Arguments:
            task_id {str} -- task_id

        Returns:
            List[Offer] -- Returns a sorted list of Offers
        """
        raise NotImplementedError()

    @abstractclassmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        """
        Returns number of offers known for the task.
        """
        raise NotImplementedError()
