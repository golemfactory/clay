from abc import ABC, abstractclassmethod
from typing import Any, Optional, List

import golem.ranking.manager.database_manager as dbm


class ProviderPerformance:
    def __init__(self, usage_benchmark):
        self.usage_benchmark = usage_benchmark


# pylint:disable=too-many-instance-attributes,too-many-public-methods
class Offer:
    # pylint:disable=too-many-arguments
    def __init__(
            self,
            offer_msg,
            provider_id: str,
            provider_performance: ProviderPerformance,
            max_price: float,
            price: float):
        self.offer_msg = offer_msg
        self.provider_id = provider_id
        self.provider_performance = provider_performance
        self.max_price = max_price
        self.price = price
        self.reputation = dbm.get_provider_efficiency(provider_id)
        self.quality = dbm.get_provider_efficacy(provider_id).vector


class RequestorMarketStrategy(ABC):

    @abstractclassmethod
    def add(cls, task_id: str, offer: Any):
        """
        Called when a WantToComputeTask arrives.
        """
        pass

    # pylint: disable-msg=line-too-long
    @abstractclassmethod
    def resolve_task_offers(cls, task_id: str,
                            key=None) -> Optional[List[Any]]:
        """
        Arguments:
            task_id {str} -- task_id

        Keyword Arguments:
            key {Optional[Callable[..., Offer]]} -- Callable used to retrieve
                Offer from given composites (default: {None})

        Returns:
            List[Any] -- Returns a sorted list of
                composites as added in `add` method.
        """
        pass

    @abstractclassmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        """
        Returns number of offers known for the task.
        """
        pass
