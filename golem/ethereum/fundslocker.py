import logging
from typing import Dict, TYPE_CHECKING

from ethereum.utils import denoms


if TYPE_CHECKING:
    from .transactionsystem import TransactionSystem  # noqa pylint:disable=unused-import

logger = logging.getLogger(__name__)


class TaskFundsLock:
    def __init__(self, subtask_price: int, num_tasks: int) -> None:
        self.price = subtask_price
        self.num_tasks = num_tasks

    @property
    def gnt_lock(self):
        return self.price * self.num_tasks


class FundsLocker:
    def __init__(
            self,
            transaction_system: 'TransactionSystem',
    ) -> None:
        self.funds: Dict[str, int] = {}
        self.transaction_system: 'TransactionSystem' = transaction_system

    def deposit(
            self,
            fund_id: str,
            amount: int
    ) -> None:
        if self.funds.get(fund_id) is not None:
            logger.error("Tried to duplicate fund with same %r", fund_id)
            return
        self.transaction_system.lock_funds_for_payments(
            funds
            1
        )
        self.funds[fund_id] = amount

    def withdraw(self, fund_id, amount):
        fund = self.funds.get(fund_id)
        if fund is None:
            logger.warning("No such fund %r.", fund_id)
            return

        assert fund >= 0
        unlock_amount = min(amount, fund)

        fund -= unlock_amount
        if fund == 0:
            del self.funds[fund_id]

        logger.info('Removing %r from fund %r', unlock_amount, fund_id)
        self.transaction_system.unlock_funds_for_payments(unlock_amount, 1)

    def remove(self, fund_id):
        fund = self.funds.pop(fund_id)
        if fund is None:
            logger.warning("No such fund %r.", fund_id)
            return
        logger.info('Removing fund for id %r', fund_id)
        self.transaction_system.unlock_funds_for_payments(fund, 1)
