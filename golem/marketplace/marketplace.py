from abc import ABC, abstractmethod
from typing import List

from dataclasses import dataclass

from golem_messages.message.tasks import (
    ReportComputedTask, WantToComputeTask
)


class ProviderPerformance:
    def __init__(self, usage_benchmark: float):
        """
        Arguments:
            usage_benchmark {float} -- Use benchmark in seconds
        """
        self.usage_benchmark: float = usage_benchmark


@dataclass
class Offer:
    provider_id: str
    provider_performance: ProviderPerformance
    max_price: float
    price: float


@dataclass
class ProviderPricing:
    price_per_wallclock_h: int
    price_per_cpu_h: int


class RequestorMarketStrategy(ABC):

    @classmethod
    @abstractmethod
    def add(cls, task_id: str, offer: Offer):
        """
        Called when a WantToComputeTask arrives.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def resolve_task_offers(cls, task_id: str) -> List[Offer]:
        """
        Arguments:
            task_id {str} -- task_id

        Returns:
            List[Offer] -- Returns a sorted list of Offers
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def get_task_offer_count(cls, task_id: str) -> int:
        """
        Returns number of offers known for the task.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def calculate_payment(cls, rct: ReportComputedTask) -> int:
        """
        determines the actual payment for the provider,
        based on the chain of messages pertaining to the computed task
        :param rct: the provider's computation report message
        :return: [ GNT wei ]
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def calculate_budget(cls, wtct: WantToComputeTask) -> int:
        """
        determines the task's budget (maximum payment),
        based on the chain of messages pertaining to the job (subtask)
        that's about to be assigned
        :param wtct: the provider's offer
        :return: [ GNT wei ]
        """
        raise NotImplementedError()


class ProviderMarketStrategy(ABC):

    SET_CPU_TIME_LIMIT: bool = False

    @classmethod
    @abstractmethod
    def calculate_price(cls, pricing: ProviderPricing, max_price: int,
                        requestor_id: str) -> int:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def calculate_payment(cls, rct: ReportComputedTask) -> int:
        """
        determines the actual payment for the provider,
        based on the chain of messages pertaining to the computed task
        :param rct: the provider's computation report message
        :return: [ GNT wei ]
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def calculate_budget(cls, wtct: WantToComputeTask) -> int:
        """
        determines the task's budget (maximum payment),
        based on the chain of messages pertaining to the job (subtask)
        that's about to be assigned
        :param wtct: the provider's offer
        :return: [ GNT wei ]
        """
        raise NotImplementedError()
