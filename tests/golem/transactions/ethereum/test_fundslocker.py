import time
from unittest import mock, TestCase

from golem.core.common import timeout_to_deadline
from golem.core.variables import PAYMENT_DEADLINE
from golem.task.taskkeeper import compute_subtask_value
from golem.transactions.ethereum.fundslocker import FundsLocker, TaskFundsLock

class TestFundsLocker(TestCase):
    def test_init(self):
        fl = FundsLocker(mock.MagicMock())
        assert isinstance(fl, FundsLocker)
        assert isinstance(fl.task_lock, dict)

    def test_lock_funds(self):
        ts =  mock.MagicMock()
        ts.eth_for_batch_payment.return_value = 139013
        fl = FundsLocker(ts)
        task_deadline = timeout_to_deadline(3600)
        fl.lock_funds("abc", 320, 10, 360, task_deadline)
        time_ = time.time()
        tfl = fl.task_lock['abc']

        def test_params(tfl):
            assert isinstance(tfl, TaskFundsLock)
            assert tfl.gnt_lock() == 320
            assert tfl.eth_lock() == 139013
            assert tfl.task_id == "abc"
            assert tfl.price == 320
            assert tfl.num_tasks == 10
            assert tfl.subtask_timeout == 360
            assert tfl.task_deadline == task_deadline
            assert time_ <= tfl.time_locked <= time.time()

        test_params(tfl)

        fl.lock_funds("abc", 111, 5, 120, task_deadline + 4)
        tfl = fl.task_lock['abc']
        test_params(tfl)

    def test_sum_locks(self):
        ts = mock.MagicMock()
        ts.eth_for_batch_payment.return_value = 13000
        fl = FundsLocker(ts)
        fl.lock_funds("abc", 320, 10, 360, timeout_to_deadline(3600))
        fl.lock_funds("def", 140, 7, 3600, timeout_to_deadline(3600))
        fl.lock_funds("ghi", 10, 4, 60, timeout_to_deadline(3600))
        fl.lock_funds("jkl", 13, 1, 3000, timeout_to_deadline(3600))
        gnt, eth = fl.sum_locks()
        assert eth == 13000 * 4
        assert gnt == compute_subtask_value(320, 360) * 10 + \
                      compute_subtask_value(140, 3600) * 7 + \
                      compute_subtask_value(10, 60) * 4 + \
                      compute_subtask_value(13, 3000)

    @mock.patch("golem.transactions.ethereum.fundslocker.time")
    def test_remove_old(self, time_mock):
        time_mock.time.return_value = time.time()
        print(time.time())
        ts = mock.MagicMock()
        ts.eth_for_batch_payment.return_value = 13000
        fl = FundsLocker(ts)
        fl.lock_funds("abc", 320, 10, 360, timeout_to_deadline(0.5))
        fl.lock_funds("def", 140, 7, 3600, timeout_to_deadline(2))
        fl.lock_funds("ghi", 10, 4, 60, timeout_to_deadline(0.2))
        fl.lock_funds("jkl", 13, 1, 3000, timeout_to_deadline(3.5))
        time_mock.time.return_value += PAYMENT_DEADLINE + 1
        fl.remove_old()
        assert fl.task_lock.get("abc") is None
        assert fl.task_lock.get("def") is not None
        assert fl.task_lock.get("ghi") is None
        assert fl.task_lock.get("jkl") is not None
