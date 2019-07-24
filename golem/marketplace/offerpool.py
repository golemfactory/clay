import sys
import logging
from typing import Any, Callable, List, Dict, ClassVar, Tuple, Optional

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
    _pools: ClassVar[Dict[str, List[Any]]] = dict()

    @classmethod
    def add(cls, task_id: str, offer: Any) -> None:
        """
        Arguments:
            task_id {str} -- task_id
            offer {Any} -- offer can be a composite (tuple,
                dict, etc.) containing Offer
        """
        if task_id not in cls._pools:
            cls._pools[task_id] = []
        cls._pools[task_id].append(offer)

    @classmethod
    def choose_offers(cls, task_id: str,
                      key: Optional[Callable[..., Offer]]=None) -> List[Any]:
        """
        Arguments:
            task_id {str} -- task_id

        Keyword Arguments:
            key {Callable[..., Offer]} -- Callable used to retrieve
                Offer from given composites (default: {None})

        Returns:
            List[Any] -- Returns a sorted list of
                composites as added in `add` method.
        """
        offers = cls._pools.pop(task_id)
        if key:
            permutation = order_providers(
                [key(offer) for offer in offers]
            )
        else:
            permutation = order_providers(offers)
        return [offers[i] for i in permutation]

    @classmethod
    def get_task_offer_count(cls, task_id: str):
        return len(cls._pools[task_id]) if task_id in cls._pools else 0

    @classmethod
    def reset(cls):
        cls._pools = {}

    @classmethod
    def clear_offers_for_task(cls, task_id):
        cls._pools.pop(task_id)
