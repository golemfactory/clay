import logging
import pickle
import time

from golem.core.service import LoopingCallService
from golem.core.variables import PAYMENT_DEADLINE
from golem.transactions.ethereum.exceptions import NotEnoughFunds

logger = logging.getLogger(__name__)


class TaskFundsLock:  # pylint: disable=too-few-public-methods
    def __init__(self, task):
        self.gnt_lock = task.price
        self.num_tasks = task.total_tasks
        self.task_deadline = task.header.deadline


class FundsLocker(LoopingCallService):
    def __init__(self, transaction_system, datadir, persist=True,
                 interval_seconds=60):
        super().__init__(interval_seconds)
        self.task_lock = {}
        self.transaction_system = transaction_system
        self.dump_path = datadir / "fundslockv1.pickle"
        self.persist = persist
        self.restore()

    def lock_funds(self, task):
        task_id = task.header.task_id
        if self.task_lock.get(task_id) is not None:
            logger.error("Tried to duplicate lock_fund with same "
                         "task_id %r", task_id)
            return

        tfl = TaskFundsLock(task)
        _, gnt, eth, _, _ = self.transaction_system.get_balance()
        lock_gnt, lock_eth = self.sum_locks()
        logger.info('Locking funds for task: %r %r %r', task_id, lock_gnt,
                    lock_eth)
        if tfl.gnt_lock > gnt - lock_gnt:
            raise NotEnoughFunds(tfl.gnt_lock, gnt - lock_gnt)

        required_eth = \
            self.transaction_system.eth_for_batch_payment(tfl.num_tasks)
        if lock_eth == 0:
            required_eth += self.transaction_system.eth_base_for_batch_payment()
        if required_eth > eth - lock_eth:
            raise NotEnoughFunds(required_eth, eth - lock_eth,
                                 extension="ETH")

        self.task_lock[task_id] = tfl
        self.dump_locks()

    def sum_locks(self):
        gnt, eth = 0, 0
        total_subtasks = 0
        for task_lock in self.task_lock.values():
            gnt += task_lock.gnt_lock
            total_subtasks += task_lock.num_tasks
        if total_subtasks > 0:
            eth = \
                self.transaction_system.eth_for_batch_payment(total_subtasks) +\
                self.transaction_system.eth_base_for_batch_payment()
        return gnt, eth

    def remove_old(self):
        time_ = time.time()
        for task_id, task in list(self.task_lock.items()):
            if task.task_deadline + PAYMENT_DEADLINE < time_:
                del self.task_lock[task_id]
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
        for task_id, task in self.task_lock.items():
            logger.info('Restoring old tasks locks: %r', task_id)

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
            return
        logger.info('Removing subtask lock for task %r', task_id)
        task_lock.num_tasks -= 1
        self.dump_locks()

    def remove_task(self, task_id):
        task_lock = self.task_lock.get(task_id)
        if task_lock is None:
            logger.warning("I can't remove payment lock from task"
                           "%r: unkown task.", task_id)
            return
        logger.info('Removing task lock %r', task_id)
        del self.task_lock[task_id]
        self.dump_locks()
