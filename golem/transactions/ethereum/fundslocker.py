import logging
import pickle
import time

from golem.core.service import LoopingCallService
from golem.core.variables import PAYMENT_DEADLINE
from golem.task.taskkeeper import compute_subtask_value
from golem.transactions.ethereum.exceptions import NotEnoughFunds

logger = logging.getLogger("golem")


class TaskFundsLock():
    def __init__(self, task_id, price, num_tasks, subtask_timeout,
                 task_deadline, transaction_system=None):
        self.task_id = task_id
        self.price = price
        self.num_tasks = num_tasks
        self.subtask_timeout = subtask_timeout
        self.task_deadline = task_deadline
        self.transaction_system = transaction_system

    def gnt_lock(self):
        price = compute_subtask_value(self.price, self.subtask_timeout)
        return (self.num_tasks) * price

    def eth_lock(self):
        if self.transaction_system is None:
            return 0
        return self.transaction_system.eth_for_batch_payment(self.num_tasks)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['transaction_system']
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self.transaction_system = None


class FundsLocker(LoopingCallService):
    def __init__(self, transaction_system, datadir, persist=True,
                 interval_seconds=60):
        super().__init__(interval_seconds)
        self.task_lock = {}
        self.transaction_system = transaction_system
        self.dump_path = datadir / "fundslock.pickle"
        self.persist = persist
        self.restore()

    def lock_funds(self, task_id, price, num_tasks, subtask_timeout,
                   task_deadline):
        if self.task_lock.get(task_id) is not None:
            logger.error("Tried to duplicate lock_fund with same "
                         "task_id %r", task_id)
            return

        tfl = TaskFundsLock(task_id, price, num_tasks, subtask_timeout,
                            task_deadline, self.transaction_system)
        _, gnt, eth, _, _ = self.transaction_system.get_balance()
        lock_gnt, lock_eth = self.sum_locks()
        if tfl.gnt_lock() > gnt - lock_gnt:
            raise NotEnoughFunds(tfl.gnt_lock(), gnt - lock_gnt)

        if tfl.eth_lock() > eth - lock_eth:
            raise NotEnoughFunds(tfl.eth_lock(), eth - lock_eth,
                                 extension="ETH")

        self.task_lock[task_id] = tfl
        self.dump_locks()

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
        self.dump_locks()

    def _run(self):
        self.remove_old()

    def restore(self):
        if not self.persist:
            return
        if not self.dump_path.exists():
            return
        with self.dump_path.open('rb') as f:
            try:
                self.task_lock = pickle.load(f)
            except (pickle.UnpicklingError, EOFError, AttributeError, KeyError):
                logger.exception("Problem restoring dumpfile: %s",
                                 self.dump_path)
                return
        for task in self.task_lock.values():
            task.transaction_system = self.transaction_system

    def dump_locks(self):
        if not self.persist:
            return
        with self.dump_path.open('wb') as f:
            pickle.dump(self.task_lock, f)

    def remove_subtask(self, task_id):
        task_lock = self.task_lock.get(task_id)
        if task_lock is None:
            logger.warning("I can't remove payment lock for subtask from task"
                           "%r: unkown task.", task_id)
        task_lock.num_tasks -= 1
