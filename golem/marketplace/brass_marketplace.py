from abc import ABC, abstractclassmethod
import sys
import logging
from typing import List, Dict, ClassVar, Tuple, Optional

import golem.ranking.manager.database_manager as dbm

from .rust import order_providers

logger = logging.getLogger(__name__)


def scale_price(task_price: float, offered_price: float) -> float:
    if offered_price == 0:
        # using float('inf') breaks math in order_providers, when alpha < 1
        return sys.float_info.max
    return task_price / offered_price


class ProviderStats:
    def __init__(self, usage_benchmark):
        self.usage_benchmark = usage_benchmark


class BrassMarketOffer:
    def __init__(self, scaled_price, reputation, quality):
        self.scaled_price = scaled_price
        self.reputation = reputation
        self.quality = quality


class Offer:
    def __init__(
            self,
            offer_msg,
            task_id: str,
            provider_id: str,
            provider_stats: ProviderStats,
            max_price: float,
            price: float):
        self.offer_msg = offer_msg
        self.task_id = task_id
        self.provider_id = provider_id
        self.provider_stats = provider_stats
        self.max_price = max_price
        self.price = price
        self.reputation = dbm.get_provider_efficiency(provider_id)
        self.quality = dbm.get_provider_efficacy(provider_id).vector


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

    @abstractclassmethod
    def report_subtask_usages(cls,
                              subtask_id: str,
                              usages: List[Tuple[str, float]]) -> None:
        """
        Report resource usages for a subtask
        :param subtask_id: id of the reported subtask
        :param usages: list of pairs (provider_id, usage)
        """
        pass

    @abstractclassmethod
    def report_task_usages(cls,
                           task_id: str,
                           usages: List[Tuple[str, float]]) -> None:
        """
        Report resource usages for a task
        :param task_id: id of the reported task
        :param usages: list of pairs (provider_id, usage)
        """
        pass


class RequestorPoolingMarketStrategy(RequestorMarketStrategy):

    _pools: ClassVar[Dict[str, List[Offer]]] = dict()

    @classmethod
    def add(cls, offer: Offer):
        if offer.task_id not in cls._pools:
            cls._pools[offer.task_id] = []
        cls._pools[offer.task_id].append(offer)

        logger.debug(
            "Offer accepted & added to pool. offer=%s",
            offer,
        )

    @classmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        return len(cls._pools[task_id]) if task_id in cls._pools else 0

    @classmethod
    def clear_offers_for_task(cls, task_id) -> None:
        if task_id in cls._pools:
            _ = cls._pools.pop(task_id)

    @classmethod
    def reset(cls) -> None:
        cls._pools = dict()


class RequestorBrassMarketStrategy(RequestorPoolingMarketStrategy):
    @classmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        logger.info("Ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return None

        order = order_providers(
            [BrassMarketOffer(scale_price(offer.max_price, offer.price),
                              offer.reputation, offer.quality)
             for offer in cls._pools[task_id]]
        )

        offers_sorted = []
        offers = cls._pools.pop(task_id)
        for index in order:
            offers_sorted.append(offers[index])

        return offers_sorted
