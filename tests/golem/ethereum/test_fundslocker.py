from unittest import mock, TestCase

from golem.ethereum.fundslocker import (
    logger,
    FundsLocker,
    TaskFundsLock,
)


class TestFundsLocker(TestCase):
    def setUp(self):
        self.ts = mock.Mock()

    def test_init(self):
        fl = FundsLocker(self.ts)
        assert isinstance(fl.task_lock, dict)

    def test_lock_funds(self):
        fl = FundsLocker(self.ts)
        task_id = "abc"
        subtask_price = 320
        num_tasks = 10
        fl.lock_funds(task_id, subtask_price, num_tasks)
        self.ts.lock_funds_for_payments.assert_called_once_with(
            subtask_price, num_tasks)
        tfl = fl.task_lock[task_id]

        def test_params(tfl):
            assert isinstance(tfl, TaskFundsLock)
            assert tfl.gnt_lock == subtask_price * num_tasks
            assert tfl.num_tasks == num_tasks

        test_params(tfl)

        fl.lock_funds(task_id, subtask_price + 1, num_tasks + 1)
        tfl = fl.task_lock[task_id]
        test_params(tfl)

    @staticmethod
    def _add_tasks(fl):
        fl.lock_funds("abc", 320, 10)
        fl.lock_funds("def", 140, 7)
        fl.lock_funds("ghi", 10, 4)
        fl.lock_funds("jkl", 13, 1)

    def test_exception(self):
        def _throw(*_):
            raise Exception("test exc")
        self.ts.lock_funds_for_payments.side_effect = _throw
        fl = FundsLocker(self.ts)
        with self.assertRaisesRegex(Exception, "test exc"):
            fl.lock_funds("task_id", 10, 5)

    def test_remove_task(self):
        fl = FundsLocker(self.ts)
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
        fl = FundsLocker(self.ts)
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
        fl = FundsLocker(self.ts)

        task_id = "abc"
        subtask_price = 320
        num_tasks = 10
        fl.lock_funds(task_id, subtask_price, num_tasks)

        self.ts.reset_mock()

        fl.add_subtask("NONEXISTING")
        self.ts.lock_funds_for_payments.assert_not_called()

        num = 3
        fl.add_subtask(task_id, num)
        self.ts.lock_funds_for_payments.assert_called_with(subtask_price,
                                                           num)
        assert fl.task_lock[task_id].num_tasks == num_tasks + num
