import sys
import logging
from typing import List, Optional, Tuple

from dataclasses import dataclass
from golem.marketplace import Offer
from golem.marketplace.pooling_marketplace import\
    RequestorPoolingMarketStrategy

from .rust import order_providers

logger = logging.getLogger(__name__)


def scale_price(task_price: float, offered_price: float) -> float:
    if offered_price == 0:
        # using float('inf') breaks math in order_providers, when alpha < 1
        return sys.float_info.max
    return task_price / offered_price


@dataclass
class BrassMarketOffer:
    scaled_price: float
    reputation: float = .0
    quality: Tuple[float, float, float, float] = (.0, .0, .0, .0)


class RequestorBrassMarketStrategy(RequestorPoolingMarketStrategy):
    # pylint: disable-msg=line-too-long
    @classmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        logger.info("Ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return None

        offers = cls._pools.pop(task_id)

        permutation = order_providers([
            BrassMarketOffer(scale_price(offer.max_price, offer.price),
                             offer.reputation, offer.quality)
            for offer in offers
        ])

        return [offers[i] for i in permutation]

    @classmethod
    def get_payment_computer(cls, task: 'Task', subtask_id: str):
        return lambda price: price
