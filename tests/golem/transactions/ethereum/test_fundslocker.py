import time
from unittest import mock

from golem.core.common import timeout_to_deadline
from golem.core.variables import PAYMENT_DEADLINE
from golem.task.taskkeeper import compute_subtask_value
from golem.testutils import TempDirFixture
from golem.transactions.ethereum.fundslocker import FundsLocker, TaskFundsLock


class TestFundsLocker(TempDirFixture):
    def setUp(self):
        super().setUp()
        self.ts = mock.MagicMock()
        self.ts.eth_for_batch_payment.return_value = 13000
        val = 100000
        time_ = time.time()
        self.ts.get_balance.return_value = val, val, val, time_, time_

    def test_init(self):
        fl = FundsLocker(self.ts, self.new_path)
        assert isinstance(fl, FundsLocker)
        assert isinstance(fl.task_lock, dict)

    def test_lock_funds(self):
        fl = FundsLocker(self.ts, self.new_path)
        task_deadline = timeout_to_deadline(3600)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.header.max_price = 320
        task.total_tasks = 10
        task.header.subtask_timeout = 360
        task.header.deadline = task_deadline
        fl.lock_funds(task)
        tfl = fl.task_lock['abc']

        def test_params(tfl):
            assert isinstance(tfl, TaskFundsLock)
            assert tfl.gnt_lock() == 320
            assert tfl.eth_lock() == 13000
            assert tfl.task_id == "abc"
            assert tfl.price == 320
            assert tfl.num_tasks == 10
            assert tfl.subtask_timeout == 360
            assert tfl.task_deadline == task_deadline

        test_params(tfl)

        task.header.max_price = 111
        task.total_tasks = 5
        task.header.subtask_timeout = 120
        task.header.deadline = task_deadline + 4
        fl.lock_funds(task)
        tfl = fl.task_lock['abc']
        test_params(tfl)

    def test_sum_locks(self):
        fl = FundsLocker(self.ts, self.new_path)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.header.max_price = 320
        task.total_tasks = 10
        task.header.subtask_timeout = 360
        task.header.deadline = timeout_to_deadline(3600)
        fl.lock_funds(task)
        task.header.task_id = "def"
        task.header.max_price = 140
        task.total_tasks = 7
        task.header.subtask_timeout = 3600
        fl.lock_funds(task)
        task.header.task_id = "ghi"
        task.header.max_price = 10
        task.total_tasks = 4
        task.header.subtask_timeout = 60
        fl.lock_funds(task)
        task.header.task_id = "jkl"
        task.header.max_price = 13
        task.total_tasks = 1
        task.header.subtask_timeout = 3000
        fl.lock_funds(task)
        gnt, eth = fl.sum_locks()
        assert eth == 13000 * 4
        val1 = compute_subtask_value(320, 360) * 10
        val2 = compute_subtask_value(140, 3600) * 7
        val3 = compute_subtask_value(10, 60) * 4
        val4 = compute_subtask_value(13, 3000)
        assert gnt == val1 + val2 + val3 + val4

    @mock.patch("golem.transactions.ethereum.fundslocker.time")
    def test_remove_old(self, time_mock):
        time_mock.time.return_value = time.time()
        fl = FundsLocker(self.ts, self.new_path)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.header.max_price = 320
        task.total_tasks = 10
        task.header.subtask_timeout = 360
        task.header.deadline = timeout_to_deadline(0.5)
        fl.lock_funds(task)
        task.header.task_id = "def"
        task.header.max_price = 140
        task.total_tasks = 7
        task.header.subtask_timeout = 3600
        task.header.deadline = timeout_to_deadline(2)
        fl.lock_funds(task)
        task.header.task_id = "ghi"
        task.header.max_price = 10
        task.total_tasks = 4
        task.header.subtask_timeout = 60
        task.header.deadline = timeout_to_deadline(0.2)
        fl.lock_funds(task)
        task.header.task_id = "jkl"
        task.header.max_price = 13
        task.total_tasks = 1
        task.header.subtask_timeout = 3000
        task.header.deadline = timeout_to_deadline(3.5)
        fl.lock_funds(task)
        time_mock.time.return_value += PAYMENT_DEADLINE + 1
        fl.remove_old()
        assert fl.task_lock.get("abc") is None
        assert fl.task_lock.get("def") is not None
        assert fl.task_lock.get("ghi") is None
        assert fl.task_lock.get("jkl") is not None

    def test_dump_and_restore(self):
        fl = FundsLocker(self.ts, self.new_path)

        # we should dump tasks after every lock
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.header.max_price = 320
        task.total_tasks = 10
        task.header.subtask_timeout = 360
        task.header.deadline = timeout_to_deadline(0.5)
        fl.lock_funds(task)
        task.header.task_id = "def"
        task.header.max_price = 140
        task.total_tasks = 7
        task.header.subtask_timeout = 3600
        task.header.deadline = timeout_to_deadline(2)
        fl.lock_funds(task)
        task.header.task_id = "ghi"
        task.header.max_price = 10
        task.total_tasks = 4
        task.header.subtask_timeout = 60
        task.header.deadline = timeout_to_deadline(0.2)
        fl.lock_funds(task)
        task.header.task_id = "jkl"
        task.header.max_price = 13
        task.total_tasks = 1
        task.header.subtask_timeout = 3000
        task.header.deadline = timeout_to_deadline(3.5)
        fl.lock_funds(task)

        # new fund locker should restore tasks
        fl2 = FundsLocker(self.ts, self.new_path)
        assert len(fl2.task_lock) == 4
        assert fl2.task_lock['abc'].price == 320
        assert fl2.task_lock['def'].transaction_system == self.ts
        assert fl2.task_lock['ghi'].eth_lock() == 13000
        assert fl2.task_lock['jkl'].gnt_lock() == compute_subtask_value(13,
                                                                        3000)
