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
        self.task_lock: Dict[str, TaskFundsLock] = {}
        self.transaction_system: 'TransactionSystem' = transaction_system

    def lock_funds(
            self,
            task_id: str,
            subtask_price: int,
            num_tasks: int,
    ) -> None:
        if self.task_lock.get(task_id) is not None:
            logger.error("Tried to duplicate lock_fund with same "
                         "task_id %r", task_id)
            return

        tfl = TaskFundsLock(subtask_price, num_tasks)
        logger.info(
            'Locking funds for task: %r price: %.3f GNTB num: %d',
            task_id,
            tfl.price / denoms.ether,
            tfl.num_tasks,
        )
        self.transaction_system.lock_funds_for_payments(
            tfl.price,
            tfl.num_tasks,
        )
        self.task_lock[task_id] = tfl

    def remove_subtask(self, task_id):
        task_lock = self.task_lock.get(task_id)
        if task_lock is None:
            logger.warning("I can't remove payment lock for subtask from task"
                           "%r: unkown task.", task_id)
            return
        logger.info('Removing subtask lock for task %r', task_id)
        task_lock.num_tasks -= 1
        self.transaction_system.unlock_funds_for_payments(task_lock.price, 1)

    def remove_task(self, task_id):
        task_lock = self.task_lock.get(task_id)
        if task_lock is None:
            logger.warning("I can't remove payment lock from task"
                           "%r: unkown task.", task_id)
            return
        logger.info('Removing task lock %r', task_id)
        del self.task_lock[task_id]
        self.transaction_system.unlock_funds_for_payments(
            task_lock.price,
            task_lock.num_tasks,
        )

    def add_subtask(self, task_id, num=1):
        task_lock = self.task_lock.get(task_id)
        if task_lock is None:
            logger.warning("I can't add payment lock for subtask from task "
                           "%r: unkown task.", task_id)
            return
        logger.info('Adding subtask lock for task %r', task_id)
        task_lock.num_tasks += num
        self.transaction_system.lock_funds_for_payments(task_lock.price, num)

    def has_task(self, task_id):
        return task_id in self.task_lock
