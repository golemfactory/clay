import logging
from typing import List, Dict, ClassVar, Tuple, Optional

from golem.marketplace.marketplace import Offer
from golem.marketplace.pooling_marketplace import\
    RequestorPoolingMarketStrategy


logger = logging.getLogger(__name__)


class RequestorWasmMarketStrategy(RequestorPoolingMarketStrategy):

    _usage_factors: ClassVar[Dict[str, float]] = dict()
    _max_usage_factor: ClassVar[float] = 2.0

    @classmethod
    def get_my_usage_benchmark(cls):
        return 1.0

    @classmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        logger.info("RWMS ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return None

        max_factor: float = cls._max_usage_factor
        offers: List[Offer] = cls._pools.pop(task_id)
        to_sort: List[Tuple[Offer, float, float]] = []
        for offer in offers:
            usage_factor = cls._usage_factors.get(offer.provider_id, None)
            if usage_factor is None:
                usage_factor = offer.provider_stats.usage_benchmark / cls.get_my_usage_benchmark()
                if not usage_factor:
                    usage_factor = 1.0
                cls._usage_factors[offer.provider_id] = usage_factor
            adjusted_price = usage_factor * offer.price
            to_sort.append((offer, usage_factor, adjusted_price))
        offers_sorted = [t[0] for t in sorted(to_sort, key=lambda t: t[2]) if t[1] <= max_factor]
        return offers_sorted
