from abc import ABC, abstractclassmethod
from typing import Callable, Optional, List, Tuple

from dataclasses import dataclass

import golem.ranking.manager.database_manager as dbm


class ProviderPerformance:
    def __init__(self, usage_benchmark):
        self.usage_benchmark = usage_benchmark


@dataclass
class Offer:
    provider_id: str
    provider_performance: ProviderPerformance
    max_price: float
    price: float
    reputation: float = .0
    quality: Tuple[float, float, float, float] = (.0, .0, .0, .0)

    def __post_init__(self):
        self.reputation = dbm.get_provider_efficiency(self.provider_id)
        self.quality = dbm.get_provider_efficacy(self.provider_id).vector


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

    @abstractclassmethod
    def get_payment_computer(cls, task: Task, subtask_id: str)\
            -> Callable[[float], float]:
        """Returns a function computing payment based on price in TTC.
        Raises:
            NotImplementedError: [description]

        Returns:
            Callable[[float], float] -- Function computing payment
        """
        raise NotImplementedError()
