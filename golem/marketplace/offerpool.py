import logging
from typing import List, Dict, ClassVar, Tuple

from twisted.internet import task
from twisted.internet.defer import Deferred

from .rust import order_providers

logger = logging.getLogger(__name__)


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

    _INTERVAL: ClassVar[float] = 15.0  # s
    _pools: ClassVar[Dict[str, List[Tuple[Offer, Deferred]]]] = dict()

    @classmethod
    def change_interval(cls, interval: float) -> None:
        logger.info("Offer pooling interval set to %.1f", interval)
        cls._INTERVAL = interval

    @classmethod
    def add(cls, task_id: str, offer: Offer) -> Deferred:
        if task_id not in cls._pools:
            logger.info(
                "Will select providers for task %s in %.1f seconds",
                task_id,
                cls._INTERVAL,
            )
            cls._pools[task_id] = []

            def _on_error(e):
                logger.error(
                    "Error while choosing providers for task %s: %r",
                    task_id,
                    e,
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
        logger.info("Ordering providers for task: %s", task_id)
        offers = cls._pools.pop(task_id)
        order = order_providers(list(map(lambda x: x[0], offers)))
        for i in order:
            offers[i][1].callback(True)
