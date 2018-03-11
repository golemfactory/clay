import logging
import time

from golem.core.service import LoopingCallService
from golem.core.variables import PAYMENT_DEADLINE
from golem.task.taskkeeper import compute_subtask_value

logger = logging.getLogger("golem")


class TaskFundsLock():
    def __init__(self, task_id, price, num_tasks, subtask_timeout,
                 task_deadline, transaction_system):
        self.task_id = task_id
        self.price = price
        self.num_tasks = num_tasks
        self.subtask_timeout = subtask_timeout
        self.task_deadline = task_deadline
        self.transaction_system = transaction_system

    def gnt_lock(self):
        price = compute_subtask_value(self.price, self.subtask_timeout)
        return (self.num_tasks)  * price

    def eth_lock(self):
        return self.transaction_system.eth_for_batch_payment(self.num_tasks)


class FundsLocker(LoopingCallService):
    def __init__(self, transaction_system, interval_seconds=60):
        super().__init__(interval_seconds)
        self.task_lock = {}
        self.transaction_system = transaction_system

    def lock_funds(self, task_id, price, num_tasks, subtask_timeout,
                   task_deadline):
        if self.task_lock.get(task_id) is not None:
            logger.error("Tried to duplicate lock_fund with same "
                         "task_id %r", task_id)
            return

        self.task_lock[task_id] = TaskFundsLock(task_id, price, num_tasks,
                                                  subtask_timeout,
                                                  task_deadline,
                                                  self.transaction_system)

    def sum_locks(self):
        gnt, eth = 0, 0
        for task_lock in self.task_lock.values():
            gnt += task_lock.gnt_lock()
            eth += task_lock.eth_lock()
        return gnt, eth

    def remove_old(self):
        time_ = time.time()
        for task in list(self.task_lock.values()):
            if task.task_deadline + PAYMENT_DEADLINE < time_:
                del self.task_lock[task.task_id]


    def _run(self):
        self.remove_old()