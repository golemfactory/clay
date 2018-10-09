import logging
from typing import List, Dict, Any, ClassVar

from twisted.internet import task
from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)


class Offer:
    def __init__(self, msg: Any, deferred: Deferred) -> None:
        self.msg = msg
        self.deferred = deferred


class OfferPool:

    _INTERVAL: ClassVar[float] = 15.0  # s
    _pools: ClassVar[Dict[str, List[Offer]]] = dict()

    @classmethod
    def add(cls, task_id: str, msg: Any) -> Deferred:
        if task_id not in cls._pools:
            cls._pools[task_id] = []
            from twisted.internet import reactor
            task.deferLater(reactor, cls._INTERVAL, cls._choose_offers, task_id)
        deferred = Deferred()
        cls._pools[task_id].append(Offer(msg, deferred))
        return deferred

    @classmethod
    def _choose_offers(cls, task_id: str) -> None:
        logger.info("Ordering providers for task: %s", task_id)
        offers = cls._pools[task_id]
        del cls._pools[task_id]
        # TODO call marketplace module to order offers wrt preferences
        # Right now, it's FIFO as it used to be
        for offer in offers:
            offer.deferred.callback(True)
