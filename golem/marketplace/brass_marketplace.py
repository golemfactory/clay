import sys
import logging
from typing import List, Tuple

from dataclasses import dataclass

from ethereum.utils import denoms

from golem_messages.message.tasks import (
    ReportComputedTask, WantToComputeTask
)

from golem.marketplace import (Offer, ProviderMarketStrategy, ProviderPricing)
from golem.marketplace.pooling_marketplace import\
    RequestorPoolingMarketStrategy
from golem.task import timer
from golem.task.helpers import calculate_subtask_payment
import golem.ranking.manager.database_manager as dbm

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
    def resolve_task_offers(cls, task_id: str) -> List[Offer]:
        logger.info("Ordering providers for task: %s", task_id)
        if task_id not in cls._pools:
            return []

        offers = cls._pools.pop(task_id)

        permutation = order_providers([
            BrassMarketOffer(  # type: ignore
                scale_price(offer.max_price, offer.price),
                dbm.get_provider_efficiency(offer.provider_id),
                dbm.get_provider_efficacy(offer.provider_id).vector)
            for offer in offers
        ])

        return [offers[i] for i in permutation]

    @classmethod
    def calculate_payment(cls, rct: ReportComputedTask) -> int:
        return _calculate_brass_payment(rct)

    @classmethod
    def calculate_budget(cls, wtct: WantToComputeTask) -> int:
        return _calculate_brass_budget(wtct)


class ProviderBrassMarketStrategy(ProviderMarketStrategy):

    @classmethod
    def calculate_price(
            cls,
            pricing: ProviderPricing,
            max_price: int,
            requestor_id: str
    ) -> int:
        """
        Provider's subtask price function as proposed in
        https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
        """
        r = pricing.price_per_wallclock_h *\
            (1.0 + timer.ProviderTimer.profit_factor)
        v_paid = dbm.get_requestor_paid_sum(requestor_id)
        v_assigned = dbm.get_requestor_assigned_sum(requestor_id)
        c = pricing.price_per_wallclock_h
        Q = min(1.0, (pricing.price_per_wallclock_h + 1 + v_paid + c) /
                (pricing.price_per_wallclock_h + 1 + v_assigned))
        R = dbm.get_requestor_efficiency(requestor_id)
        S = Q * R
        return min(max(int(r / S), pricing.price_per_wallclock_h), max_price)

    @classmethod
    def calculate_payment(cls, rct: ReportComputedTask) -> int:
        return _calculate_brass_payment(rct)

    @classmethod
    def calculate_budget(cls, wtct: WantToComputeTask) -> int:
        return _calculate_brass_budget(wtct)


def _calculate_brass_payment(rct: ReportComputedTask) -> int:
    task_header = rct.task_to_compute.want_to_compute_task.task_header
    price = rct.task_to_compute.want_to_compute_task.price
    timeout = task_header.subtask_timeout

    payment = calculate_subtask_payment(price, timeout)

    logger.debug(
        "Calculated Brass marketplace job payment "
        "(based on price=%s GNT/hour, timeout=%s s): %s GNT",
        price / denoms.ether,
        timeout,
        payment / denoms.ether,
    )
    return payment


def _calculate_brass_budget(wtct: WantToComputeTask) -> int:
    price = wtct.price
    timeout = wtct.task_header.subtask_timeout

    budget = calculate_subtask_payment(price, timeout)

    logger.debug(
        "Calculated Brass marketplace job budget "
        "(based on price=%s GNT/hour, timeout=%s s): %s GNT",
        price / denoms.ether,
        timeout,
        budget / denoms.ether,
    )
    return budget
