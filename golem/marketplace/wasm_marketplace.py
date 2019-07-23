import logging
from typing import List, Dict, ClassVar, Tuple, Optional, Iterable
import numpy

from golem.marketplace.marketplace import Offer
from golem.marketplace.pooling_marketplace import\
    RequestorPoolingMarketStrategy


logger = logging.getLogger(__name__)


class RequestorWasmMarketStrategy(RequestorPoolingMarketStrategy):

    _usage_factors: ClassVar[Dict[str, float]] = dict()
    _max_usage_factor: ClassVar[float] = 2.0
    _my_usage_benchmark: ClassVar[float] = 1.0
    @classmethod
    def reset(cls) -> None:
        super().reset()
        cls._usage_factors = dict()

    @classmethod
    def get_my_usage_benchmark(cls) -> float:
        return cls._my_usage_benchmark

    @classmethod
    def set_my_usage_benchmark(cls, benchmark: float) -> None:
        cls._my_usage_benchmark = benchmark


    @classmethod
    def get_usage_factor(cls, provider_id, usage_benchmark):
        usage_factor = cls._usage_factors.get(provider_id, None)
        if usage_factor is None:
            usage_factor = usage_benchmark / cls.get_my_usage_benchmark()
            if not usage_factor:
                usage_factor = 1.0
            cls._usage_factors[provider_id] = usage_factor
        return usage_factor

    @classmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        logger.info("RWMS ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return None

        max_factor: float = cls._max_usage_factor
        offers: List[Offer] = cls._pools.pop(task_id)
        to_sort: List[Tuple[Offer, float, float]] = []
        for offer in offers:
            usage_factor = cls.get_usage_factor(
                offer.provider_id,
                offer.provider_stats.usage_benchmark)
            adjusted_price = usage_factor * offer.price
            to_sort.append((offer, usage_factor, adjusted_price))
        offers_sorted = [t[0] for t in sorted(to_sort, key=lambda t: t[2]) if t[1] <= max_factor]
        return offers_sorted

    @classmethod
    def report_subtask_usages(cls,
                              task_id: str,
                              usages: List[Tuple[str, float]]) -> None:
        if len(usages) < 2:
            return

        ds: Dict[str, float] = dict()
        deltas: Dict[str, float] = dict()
        for pid, u in usages:
            r = cls.get_usage_factor(pid, cls.get_my_usage_benchmark())
            assert r > 0
            ds[pid] = u / r

        d = geomean(ds.values())
        assert d > 0
        #deltas = {pid: di / d for pid, di in ds}
        for pid, di in ds.items():
            deltas[pid] = di / d

        for pid, delta in deltas.items():
            r = delta * cls._usage_factors[pid]
            cls._usage_factors[pid] = r
            if r > cls._max_usage_factor:
                logger.info("Provider %s has excessive usage factor: %f", pid, r)

def geomean(a: Iterable[float]) -> float:
    if not a:
        return 1.0
    if numpy.prod(a) == 0.0:
        return 0.0

    log_a = numpy.log(numpy.array(list(a)))
    return numpy.exp(log_a.mean())
