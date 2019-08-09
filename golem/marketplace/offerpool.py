import json
import sys
import logging
import threading
from typing import List, Dict, ClassVar, Tuple

from golem_messages.message import WantToComputeTask
from twisted.internet import task
from twisted.internet.defer import Deferred

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
            quality: Tuple[float, float, float, float],
            provider_id,
            want_to_compute_task_msg: WantToComputeTask

    ) -> None:
        self.scaled_price = scaled_price
        self.reputation = reputation
        self.quality = quality
        self.provider_id = provider_id
        self.want_to_compute_task_msg = want_to_compute_task_msg

    def __str__(self):
        return json.dumps({
            'provider-node-id': self.provider_id,
            'reputation': self.reputation,
            'quality': self.quality,
            'scaled_price': self.scaled_price
        }, indent=2)


class OfferPool:

    _INTERVAL: ClassVar[float] = 15.0  # s
    _pools: ClassVar[Dict[str, List[Tuple[Offer, Deferred]]]] = dict()
    _lock = threading.Lock()

    @classmethod
    def change_interval(cls, interval: float) -> None:
        logger.info("Offer pooling interval set to %.1f", interval)
        cls._INTERVAL = interval

    @classmethod
    def add(cls, task_id: str, offer: Offer, is_provider_chosen_manually=False) \
            -> Deferred:
        with cls._lock:
            if task_id not in cls._pools:
                cls._pools[task_id] = []

                def _on_error(e):
                    logger.error(
                        "Error while choosing providers for task %s: %r",
                        task_id,
                        e,
                    )
                if not is_provider_chosen_manually:
                    logger.info(
                        "Will select providers for task %s in %.1f seconds",
                        task_id,
                        cls._INTERVAL,
                    )
                    from twisted.internet import reactor
                    task.deferLater(
                        reactor,
                        cls._INTERVAL,
                        cls._choose_offers,
                        task_id,
                    ).addErrback(_on_error)

            deferred = Deferred()
            cls._pools[task_id].append((offer, deferred))
            return deferred

    @classmethod
    def _choose_offers(cls, task_id: str) -> None:
        with cls._lock:
            logger.info("Ordering providers for task: %s", task_id)
            offers = cls._pools.pop(task_id)
            order = order_providers(list(map(lambda x: x[0], offers)))
            for i in order:
                offers[i][1].callback(True)

    @classmethod
    def get_offers(cls, task_id: str) -> list:
        with cls._lock:
            return list(map(lambda offer: offer[0], cls._pools.get(task_id, []))
                        )

    @classmethod
    def get_offer(cls, task_id: str, num: int) -> Offer:
            if num < 0 or num > len(cls._pools):
                raise IndexError('{} is invalid index [size of offer pool '
                                 'is {}]'.format(num, len(cls._pools)))
            return cls.get_offers(task_id)[num][0]

    @classmethod
    def pop_offer(cls, task_id, offer_num):
        with cls._lock:
            offer = cls._pools[task_id][offer_num][0]
            del  cls._pools[task_id][offer_num]
            return offer
