import logging
from typing import (List, Dict, ClassVar, Tuple, Optional, Iterable,
                    TYPE_CHECKING)
import math
import numpy

from golem.marketplace.marketplace import (Offer, ProviderMarketStrategy,
                                           ProviderPricing)
from golem.marketplace.pooling_marketplace import\
    RequestorPoolingMarketStrategy
from golem.task import timer
from golem.task.helpers import calculate_subtask_payment
from golem.ranking.manager.database_manager import (
    get_requestor_assigned_sum,
    get_requestor_paid_sum,
)
from golem import model

if TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from golem_messages.message.tasks import ReportComputedTask

ProviderId = str
SubtaskId = str
Usage = float
UsageReport = Tuple[ProviderId, SubtaskId, Usage]

NANOSECOND = 1e-9

logger = logging.getLogger(__name__)


USAGE_SECOND = 1e9  # Usage is measured in nanoseconds


class RequestorWasmMarketStrategy(RequestorPoolingMarketStrategy):
    DEFAULT_USAGE_BENCHMARK: float = 1.0 * USAGE_SECOND

    _usages: ClassVar[Dict[str, float]] = dict()
    _max_usage_factor: ClassVar[float] = 2.0
    _my_usage_benchmark: ClassVar[float] = DEFAULT_USAGE_BENCHMARK

    @classmethod
    def get_my_usage_benchmark(cls) -> float:
        return cls._my_usage_benchmark

    @classmethod
    def set_my_usage_benchmark(cls, benchmark: float) -> None:
        if benchmark < 1e-6 * USAGE_SECOND:
            benchmark = cls.DEFAULT_USAGE_BENCHMARK
        logger.info("RWMS: set_my_usage_benchmark %.3f", benchmark)
        cls._my_usage_benchmark = benchmark

    @classmethod
    def get_usage_factor(cls, provider_id, usage_benchmark):
        usage_factor = model.UsageFactor.select().where(
            model.UsageFactor.provider_node_id == provider_id).first()
        if usage_factor is None:
            uf = usage_benchmark / cls.get_my_usage_benchmark()

            # Sanity check against misreported benchmarks
            uf = min(max(uf, 0.1), 2.0)
            logger.info("RWMS: initial usage factor for %s = %.3f",
                        provider_id,
                        uf)

            node, _ = model.ComputingNode.get_or_create(
                node_id=provider_id, defaults={'name': ''})
            usage_factor, _ = model.UsageFactor.get_or_create(
                provider_node=node,
                defaults={'usage_factor': uf})
        return usage_factor.usage_factor

    @classmethod
    def update_usage_factor(cls, provider_id: str, delta: float):
        usage_factor = model.UsageFactor.select().where(
            model.UsageFactor.provider_node_id == provider_id).first()

        r = delta * usage_factor.usage_factor
        logger.info("RWMS: adjust R for provider %s: %.3f -> %.3f",
                    provider_id[:8], usage_factor.usage_factor, r)
        usage_factor.usage_factor = r
        usage_factor.save()
        if r > cls._max_usage_factor:
            logger.info("RWMS: Provider %s has excessive usage factor: %f",
                        provider_id, r)

    # pylint: disable-msg=line-too-long
    @classmethod
    def resolve_task_offers(cls, task_id: str) -> Optional[List[Offer]]:
        logger.info("RWMS: ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return None

        max_factor: float = cls._max_usage_factor
        offers: List[Offer] = cls._pools.pop(task_id)
        to_sort: List[Tuple[Offer, float, float]] = []

        for offer in offers:
            usage_factor = cls.get_usage_factor(
                offer.provider_id,
                offer.provider_performance.usage_benchmark)
            adjusted_price = usage_factor * offer.price
            logger.info(
                "RWMS: offer from %s, b=%.1f, R=%.3f, price=%d Gwei, a=%g",
                offer.provider_id[:8],
                offer.provider_performance.usage_benchmark,
                usage_factor,
                offer.price/10**9,
                adjusted_price)
            to_sort.append((offer, usage_factor, adjusted_price))
        offers_sorted = [t[0] for t in sorted(to_sort, key=lambda t: t[2])
                         if t[1] <= max_factor]

        return offers_sorted

    @classmethod
    def report_subtask_usages(cls,
                              _task_id: str,
                              usages: List[UsageReport]) -> None:
        assert len(usages) > 1

        for pid, sid, usage in usages:
            cls._usages[sid] = usage

        ds: Dict[str, float] = dict()
        deltas: Dict[str, float] = dict()
        for pid, _, u in usages:
            r = cls.get_usage_factor(pid, cls.get_my_usage_benchmark())
            assert r > 0
            ds[pid] = u / r

        d = geomean(ds.values())
        assert d > 0
        # deltas = {pid: di / d for pid, di in ds}
        for pid, di in ds.items():
            deltas[pid] = di / d

        for pid, delta in deltas.items():
            cls.update_usage_factor(pid, delta)

    @classmethod
    def _reset_usage_factors(cls):
        model.UsageFactor.delete().execute()

    @classmethod
    def reset(cls) -> None:
        cls._reset_usage_factors()
        cls._my_usage_benchmark = cls.DEFAULT_USAGE_BENCHMARK

    @classmethod
    def _get_subtask_usage(cls, subtask_id: str) -> float:
        """
        Returns:
            float -- Returns usage in seconds
        """
        return cls._usages.pop(subtask_id)

    @classmethod
    def calculate_payment(cls, rct: 'ReportComputedTask') -> int:
        return _calculate_usage_payment(rct)


def geomean(a: Iterable[float]) -> float:
    if not a:
        return 1.0
    if numpy.prod(a) == 0.0:
        return 0.0

    log_a = numpy.log(numpy.array(list(a)))
    return numpy.exp(log_a.mean())


class ProviderWasmMarketStrategy(ProviderMarketStrategy):

    @classmethod
    def calculate_price(cls, pricing: ProviderPricing, max_price: int,
                        requestor_id: str) -> int:
        r = pricing.price_per_cpu_h * (1.0 + timer.ProviderTimer.profit_factor)
        v_paid = get_requestor_paid_sum(requestor_id)
        v_assigned = get_requestor_assigned_sum(requestor_id)
        c = pricing.price_per_cpu_h
        Q = min(1.0, (pricing.price_per_cpu_h + 1 + v_paid + c) /
                (pricing.price_per_cpu_h + 1 + v_assigned))
        return min(max(int(r / Q), pricing.price_per_cpu_h), max_price)

    @classmethod
    def calculate_payment(cls, rct: 'ReportComputedTask') -> int:
        return _calculate_usage_payment(rct)


def _calculate_usage_payment(rct: 'ReportComputedTask') -> int:
    task_header = rct.task_to_compute.want_to_compute_task.task_header
    max_payment = calculate_subtask_payment(
        task_header.max_price,
        task_header.subtask_timeout,
    )

    usage = math.ceil(
        rct.stats.cpu_stats.cpu_usage['total_usage'] * NANOSECOND
    )
    price = rct.task_to_compute.want_to_compute_task.price

    return min(calculate_subtask_payment(price, usage), max_payment)
