import time
from unittest import mock

from golem.core.common import timeout_to_deadline
from golem.core.variables import PAYMENT_DEADLINE
from golem.testutils import TempDirFixture
from golem.transactions.ethereum.fundslocker import (logger, FundsLocker,
                                                     TaskFundsLock)


class TestFundsLocker(TempDirFixture):
    def setUp(self):
        super().setUp()
        self.ts = mock.MagicMock()
        self.ts.eth_for_batch_payment.side_effect = lambda n: n * 13000
        self.ts.eth_base_for_batch_payment.return_value = 3000
        val = 1000000
        time_ = time.time()
        self.ts.get_balance.return_value = val, val, val, time_, time_

    def test_init(self):
        fl = FundsLocker(self.ts, self.new_path)
        assert isinstance(fl, FundsLocker)
        assert isinstance(fl.task_lock, dict)

    def test_lock_funds(self):
        fl = FundsLocker(self.ts, self.new_path)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.price = 320
        task.total_tasks = 10
        fl.lock_funds(task)
        tfl = fl.task_lock['abc']

        def test_params(tfl):
            assert isinstance(tfl, TaskFundsLock)
            assert tfl.gnt_lock == 320
            assert tfl.num_tasks == 10

        test_params(tfl)

        task.header.max_price = 111
        task.total_tasks = 5
        fl.lock_funds(task)
        tfl = fl.task_lock['abc']
        test_params(tfl)

    def test_sum_locks(self):
        val1 = 320
        val2 = 140
        val3 = 10
        val4 = 13
        tasks1 = 10
        tasks2 = 7
        tasks3 = 4
        tasks4 = 1
        fl = FundsLocker(self.ts, self.new_path)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.price = val1
        task.total_tasks = tasks1
        task.header.deadline = timeout_to_deadline(3600)
        fl.lock_funds(task)
        task.header.task_id = "def"
        task.price = val2
        task.total_tasks = tasks2
        fl.lock_funds(task)
        task.header.task_id = "ghi"
        task.price = val3
        task.total_tasks = tasks3
        fl.lock_funds(task)
        task.header.task_id = "jkl"
        task.price = val4
        task.total_tasks = tasks4
        fl.lock_funds(task)
        gnt, eth = fl.sum_locks()
        assert eth == 13000 * (tasks1 + tasks2 + tasks3 + tasks4) + 3000
        assert gnt == val1 + val2 + val3 + val4

    def test_dump_and_restore(self):
        fl = FundsLocker(self.ts, self.new_path)

        # we should dump tasks after every lock
        self._add_tasks(fl)

        # new fund locker should restore tasks
        fl2 = FundsLocker(self.ts, self.new_path)
        assert len(fl2.task_lock) == 4
        assert fl2.task_lock['abc'].gnt_lock == 320

    @staticmethod
    def _add_tasks(fl):
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.price = 320
        task.total_tasks = 10
        task.header.deadline = timeout_to_deadline(0.5)
        fl.lock_funds(task)
        task.header.task_id = "def"
        task.price = 140
        task.total_tasks = 7
        task.header.deadline = timeout_to_deadline(2)
        fl.lock_funds(task)
        task.header.task_id = "ghi"
        task.price = 10
        task.total_tasks = 4
        task.header.deadline = timeout_to_deadline(0.2)
        fl.lock_funds(task)
        task.header.task_id = "jkl"
        task.price = 13
        task.total_tasks = 1
        task.header.deadline = timeout_to_deadline(3.5)
        fl.lock_funds(task)

    def test_remove_task(self):
        fl = FundsLocker(self.ts, self.new_path)
        self._add_tasks(fl)
        assert fl.task_lock['ghi']
        fl.remove_task('ghi')

        assert fl.task_lock.get('jkl')
        assert fl.task_lock.get('def')
        assert fl.task_lock.get('abc')
        assert fl.task_lock.get('ghi') is None

        with self.assertLogs(logger, level="WARNING"):
            fl.remove_task('ghi')

        assert fl.task_lock.get('ghi') is None

    def test_remove_subtask(self):
        fl = FundsLocker(self.ts, self.new_path)
        self._add_tasks(fl)
        assert fl.task_lock.get("ghi")
        assert fl.task_lock["ghi"].num_tasks == 4

        fl.remove_subtask("ghi")
        assert fl.task_lock.get("ghi")
        assert fl.task_lock["ghi"].num_tasks == 3

        with self.assertLogs(logger, level="WARNING"):
            fl.remove_subtask("NONEXISTING")
