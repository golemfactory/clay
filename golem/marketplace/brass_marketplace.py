import sys
import logging
from typing import Any, List, Optional

from golem.marketplace.pooling_marketplace import\
    RequestorPoolingMarketStrategy

from .rust import order_providers

logger = logging.getLogger(__name__)


def scale_price(task_price: float, offered_price: float) -> float:
    if offered_price == 0:
        # using float('inf') breaks math in order_providers, when alpha < 1
        return sys.float_info.max
    return task_price / offered_price


class BrassMarketOffer:
    def __init__(self, scaled_price, reputation, quality):
        self.scaled_price = scaled_price
        self.reputation = reputation
        self.quality = quality


class RequestorBrassMarketStrategy(RequestorPoolingMarketStrategy):
    # pylint: disable-msg=line-too-long
    @classmethod
    def resolve_task_offers(cls, task_id: str,
                            key=None) -> Optional[List[Any]]:
        logger.info("Ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return None

        offers = cls._pools.pop(task_id)
        if key:
            extracted_offers = [key(offer) for offer in offers]

        permutation = order_providers(
            [BrassMarketOffer(scale_price(offer.max_price, offer.price),
                              offer.reputation, offer.quality)
             for offer in extracted_offers]
        )

        return [offers[i] for i in permutation]
