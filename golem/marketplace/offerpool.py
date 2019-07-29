import sys
import logging
from typing import List, Dict, ClassVar, Tuple

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
    def add(cls, task_id: str, offer: Offer) -> None:
        if task_id not in cls._pools:
            cls._pools[task_id] = []
        cls._pools[task_id].append(offer)

    @classmethod
    def choose_offers(cls, task_id: str) -> List[Offer]:
        """
        Arguments:
            task_id {str} -- task_id
        Returns:
            List[Offer] -- Returns a sorted list of Offers
        """
        offers = cls._pools.pop(task_id)
        permutation = order_providers(offers)
        return [offers[i] for i in permutation]

    @classmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        return len(cls._pools[task_id]) if task_id in cls._pools else 0
