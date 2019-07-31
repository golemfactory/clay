import sys
import logging
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
            provider_id
    ) -> None:
        self.scaled_price = scaled_price
        self.reputation = reputation
        self.quality = quality
        self.provider_id = provider_id


class OfferPool:

    _INTERVAL: ClassVar[float] = 15.0  # s
    _pools: ClassVar[Dict[str, List[Tuple[Offer, Deferred]]]] = dict()

    @classmethod
    def change_interval(cls, interval: float) -> None:
        logger.info("Offer pooling interval set to %.1f", interval)
        cls._INTERVAL = interval

    @classmethod
    def add(cls, task_id: str, offer: Offer, is_provider_chosen_manually=False) \
            -> Deferred:
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
            else:
                logger.info('Offer {} was added to offer pool [task_id = {}]'.format(offer, task_id))

        deferred = Deferred()
        cls._pools[task_id].append((offer, deferred))
        return deferred

    @classmethod
    def _choose_offers(cls, task_id: str) -> None:
        logger.info("Ordering providers for task: %s", task_id)
        offers = cls._pools.pop(task_id)
        order = order_providers(list(map(lambda x: x[0], offers)))
        for i in order:
            offers[i][1].callback(True)

    @classmethod
    def get_offers(cls, task_id: str) -> list:
        return cls._pools.get(task_id, [])

    @classmethod
    def get_declared_providers(cls, task_id: str) -> list:
        return list(map(lambda offer: offer[0].provider_id,
                        cls.get_offers(task_id)))

    @classmethod
    def get_offer_for_provider(cls, task_id: str, provider_id) -> list:
        return list(filter(lambda offer: offer[0].provider_id == provider_id,
                           cls._pools.get(task_id, [])))
