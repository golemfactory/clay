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
        self.id = None

    def to_json(self) -> dict:
        return {
            'id': self.id,
            'provider-node-id': self.provider_id,
            'reputation': self.reputation,
            'quality': self.quality,
            'scaled_price': self.scaled_price
        }


class OfferPool:

    _INTERVAL: ClassVar[float] = 15.0  # s
    _pools: ClassVar[Dict[str, List[Tuple[Offer, Deferred]]]] = dict()
    _lock = threading.RLock()
    _counter = 0

    @classmethod
    def change_interval(cls, interval: float) -> None:
        logger.info("Offer pooling interval set to %.1f", interval)
        cls._INTERVAL = interval

    @classmethod
    def add(cls, task_id: str, offer: Offer, is_offer_chosen_manually=False) \
            -> Deferred:
        with cls._lock:
            if task_id not in cls._pools:
                cls._pools[task_id] = {}

                def _on_error(e):
                    logger.error(
                        "Error while choosing providers for task %s: %r",
                        task_id,
                        e,
                    )
                if not is_offer_chosen_manually:
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
            cls._counter = cls._counter + 1
            offer.id = cls._counter
            cls._pools[task_id][offer.id] = (offer, deferred)
            return deferred

    @classmethod
    def _choose_offers(cls, task_id: str) -> None:
        with cls._lock:
            logger.info("Ordering providers for task: %s", task_id)
            offers = list(cls._pools.pop(task_id).values())
            order = order_providers(list(map(lambda x: x[0], offers)))
            for i in order:
                offers[i][1].callback(True)

    @classmethod
    def get_offers(cls, task_id: str) -> list:
        with cls._lock:
            return list(map(lambda offer: offer[0], cls._pools.get(task_id, {})
                            .values()))

    @classmethod
    def _get_offer(cls, task_id: str, offer_id: int) -> Offer:
        with cls._lock:
            try:
                task_offers = cls._pools[task_id]
                return task_offers[offer_id][0]
            except KeyError:
                raise IndexError('{} id is invalid'.format(offer_id))

    @classmethod
    def pop_offer(cls, task_id, offer_id):
        with cls._lock:
            offer = cls._get_offer(task_id, offer_id)
            del cls._pools[task_id][offer_id]
            return offer
