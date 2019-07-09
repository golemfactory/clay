import sys
import logging
from typing import List, Dict, ClassVar, Tuple, Optional

from golem.ranking.manager.database_manager import (
    get_provider_efficacy,
    get_provider_efficiency,
)
from golem.task.taskbase import Task

from .rust import order_providers

logger = logging.getLogger(__name__)


def scale_price(task_price: float, offered_price: float) -> float:
    if offered_price == 0:
        # using float('inf') breaks math in order_providers, when alpha < 1
        return sys.float_info.max
    return task_price / offered_price


class Offer:
    def __init__(
            self,
            scaled_price: float,
            reputation: float,
            quality: Tuple[float, float, float, float]) -> None:
        self.scaled_price = scaled_price
        self.reputation = reputation
        self.quality = quality


class OfferPool:

    _pools: ClassVar[Dict[str, List[Offer]]] = dict()

    @classmethod
    def add(cls, task: Task, provider_id: str, price: float) -> None:
        if task.header.task_id not in cls._pools:
            cls._pools[task.header.task_id] = []
        offer = Offer(
            scaled_price=scale_price(task.header.max_price, price),
            reputation=get_provider_efficiency(provider_id),
            quality=get_provider_efficacy(provider_id).vector,
        )
        cls._pools[task.header.task_id].append(offer)

        logger.debug(
            "Offer accepted & added to pool. offer=%s",
            offer,
        )

    @classmethod
    def resolve_task_offers(cls, task: Task) -> Optional[List[Offer]]:
        logger.info("Ordering providers for task: %s", task.header.task_id)
        if task.header.task_id not in cls._pools:
            return None
        offers = cls._pools.pop(task.header.task_id)
        return order_providers(offers)

    @classmethod
    def get_task_offer_count(cls, task) -> int:
        return len(cls._pools[task.header.task_id]) if task.header.task_id in cls._pools else 0