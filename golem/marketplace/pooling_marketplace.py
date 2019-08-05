import logging
from typing import ClassVar, Dict, List

from golem.marketplace import RequestorMarketStrategy, Offer

logger = logging.getLogger(__name__)


class RequestorPoolingMarketStrategy(RequestorMarketStrategy):

    _pools: ClassVar[Dict[str, List[Offer]]] = dict()

    @classmethod
    def add(cls, task_id: str, offer: Offer):
        if task_id not in cls._pools:
            cls._pools[task_id] = []
        cls._pools[task_id].append(offer)

        logger.debug(
            "Offer accepted & added to pool. offer=%s",
            offer,
        )

    @classmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        return len(cls._pools[task_id]) if task_id in cls._pools else 0
