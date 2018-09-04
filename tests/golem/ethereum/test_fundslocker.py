import time
from unittest import mock

from golem.core.common import timeout_to_deadline
from golem.core.variables import PAYMENT_DEADLINE
from golem.ethereum.fundslocker import (
    logger,
    FundsLocker,
    TaskFundsLock,
)
from golem.testutils import TempDirFixture


class TestFundsLocker(TempDirFixture):
    def setUp(self):
        super().setUp()
        self.ts = mock.Mock()

    def test_init(self):
        fl = FundsLocker(self.ts, self.new_path)
        assert isinstance(fl, FundsLocker)
        assert isinstance(fl.task_lock, dict)

    def test_lock_funds(self):
        fl = FundsLocker(self.ts, self.new_path)
        task_deadline = timeout_to_deadline(3600)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.subtask_price = 320
        task.total_tasks = 10
        task.header.deadline = task_deadline
        fl.lock_funds(task)
        self.ts.lock_funds_for_payments.assert_called_once_with(320, 10)
        tfl = fl.task_lock['abc']

        def test_params(tfl):
            assert isinstance(tfl, TaskFundsLock)
            assert tfl.gnt_lock == 320 * 10
            assert tfl.num_tasks == 10
            assert tfl.task_deadline == task_deadline

        test_params(tfl)

        task.header.max_price = 111
        task.total_tasks = 5
        task.header.deadline = task_deadline + 4
        fl.lock_funds(task)
        tfl = fl.task_lock['abc']
        test_params(tfl)

    @mock.patch("golem.ethereum.fundslocker.time")
    def test_remove_old(self, time_mock):
        time_mock.time.return_value = time.time()
        fl = FundsLocker(self.ts, self.new_path)
        self._add_tasks(fl)
        time_mock.time.return_value += PAYMENT_DEADLINE + 1
        fl.remove_old()
        assert fl.task_lock.get("abc") is None
        assert fl.task_lock.get("def") is not None
        assert fl.task_lock.get("ghi") is None
        assert fl.task_lock.get("jkl") is not None

    def test_dump_and_restore(self):
        fl = FundsLocker(self.ts, self.new_path)

        # we should dump tasks after every lock
        self._add_tasks(fl)

        # new fund locker should restore tasks
        self.ts.reset_mock()
        fl2 = FundsLocker(self.ts, self.new_path)
        assert len(fl2.task_lock) == 4
        assert fl2.task_lock['abc'].gnt_lock == 320 * 10
        assert self.ts.lock_funds_for_payments.call_count == 4
        assert self.ts.lock_funds_for_payments.call_args_list[0][0] == (320, 10)
        assert self.ts.lock_funds_for_payments.call_args_list[1][0] == (140, 7)
        assert self.ts.lock_funds_for_payments.call_args_list[2][0] == (10, 4)
        assert self.ts.lock_funds_for_payments.call_args_list[3][0] == (13, 1)

    @staticmethod
    def _add_tasks(fl):
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.subtask_price = 320
        task.total_tasks = 10
        task.header.deadline = timeout_to_deadline(0.5)
        fl.lock_funds(task)
        task.header.task_id = "def"
        task.subtask_price = 140
        task.total_tasks = 7
        task.header.deadline = timeout_to_deadline(2)
        fl.lock_funds(task)
        task.header.task_id = "ghi"
        task.subtask_price = 10
        task.total_tasks = 4
        task.header.deadline = timeout_to_deadline(0.2)
        fl.lock_funds(task)
        task.header.task_id = "jkl"
        task.subtask_price = 13
        task.total_tasks = 1
        task.header.deadline = timeout_to_deadline(3.5)
        fl.lock_funds(task)

    def test_exception(self):
        self.ts.lock_funds_for_payments.side_effect = Exception
        fl = FundsLocker(self.ts, self.new_path)
        task = mock.MagicMock()
        task.header.task_id = "abc"
        task.subtask_price = 320
        task.total_tasks = 10
        task.header.deadline = timeout_to_deadline(0.5)
        with self.assertRaises(Exception):
            fl.lock_funds(task)
        self.ts.lock_funds_for_payments.reset_mock()
        # that restores locks from the storage
        fl = FundsLocker(self.ts, self.new_path)
        self.ts.lock_funds_for_payments.assert_not_called()

    def test_remove_task(self):
        fl = FundsLocker(self.ts, self.new_path, persist=False)
        self._add_tasks(fl)
        assert fl.task_lock['ghi']
        fl.remove_task('ghi')
        self.ts.unlock_funds_for_payments.assert_called_once_with(10, 4)
        self.ts.reset_mock()

        assert fl.task_lock.get('jkl')
        assert fl.task_lock.get('def')
        assert fl.task_lock.get('abc')
        assert fl.task_lock.get('ghi') is None

        with self.assertLogs(logger, level="WARNING"):
            fl.remove_task('ghi')
            self.ts.unlock_funds_for_payments.assert_not_called()

        assert fl.task_lock.get('ghi') is None

    def test_remove_subtask(self):
        fl = FundsLocker(self.ts, self.new_path, persist=False)
        self._add_tasks(fl)
        assert fl.task_lock.get("ghi")
        assert fl.task_lock["ghi"].num_tasks == 4

        fl.remove_subtask("ghi")
        self.ts.unlock_funds_for_payments.assert_called_once_with(10, 1)
        self.ts.reset_mock()
        assert fl.task_lock.get("ghi")
        assert fl.task_lock["ghi"].num_tasks == 3

        with self.assertLogs(logger, level="WARNING"):
            fl.remove_subtask("NONEXISTING")
            self.ts.unlock_funds_for_payments.assert_not_called()

    def test_add_subtask(self):
        fl = FundsLocker(self.ts, self.new_path, persist=False)

        task = mock.Mock()
        task.header.task_id = "abc"
        task.subtask_price = 320
        task.total_tasks = 10
        task.header.deadline = timeout_to_deadline(0.5)
        fl.lock_funds(task)

        self.ts.reset_mock()

        with self.assertLogs(logger, level="WARNING"):
            fl.add_subtask("NONEXISTING")
            self.ts.lock_funds_for_payments.assert_not_called()

        fl.add_subtask("abc", num=3)
        self.ts.lock_funds_for_payments.assert_called_with(320, 3)
        assert fl.task_lock["abc"].num_tasks == 13
