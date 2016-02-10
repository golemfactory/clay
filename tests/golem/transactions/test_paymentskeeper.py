import unittest

from copy import deepcopy

from golem.network.p2p.node import Node
from golem.core.keysauth import EllipticalKeysAuth
from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.assertlogs import LogTestCase
from golem.transactions.paymentskeeper import PaymentsDatabase, PaymentInfo, AccountInfo, logger, PaymentState, \
    PaymentsKeeper


class TestPaymentsDatabase(LogTestCase, TestWithDatabase):

    def test_init(self):
        pd = PaymentsDatabase("ABC")
        self.assertIsInstance(pd, PaymentsDatabase)

    def test_payments(self):
        pd = PaymentsDatabase("ABC")
        self.database.check_node("ABC")

        # test get payments
        ai = AccountInfo("DEF", 20400, "10.0.0.1", "node1", "node_info")
        pi = PaymentInfo("xyz", "xxyyzz", 20.23, ai)
        with self.assertLogs(logger, level=1) as l:
            self.assertEquals(0, pd.get_payment_value(pi))
        self.assertTrue(any(["not exist" in log for log in l.output]))
        pd.add_payment(pi)
        self.assertEquals(20.23, pd.get_payment_value(pi))
        pi = PaymentInfo("xyz", "aabbcc", 10.30, ai)
        self.assertEquals(20.23, pd.get_payment_value(pi))
        pi2 = PaymentInfo("zzz", "xxyyzz", "14.01", ai)
        pd.add_payment(pi2)
        self.assertEquals(14.01, pd.get_payment_value(pi2))
        self.assertEquals(20.23, pd.get_payment_value(pi))


        # test add_payment
        pd.add_payment(pi)
        self.assertEquals(30.53, pd.get_payment_value(pi))
        pd.add_payment(pi)
        self.assertEquals(40.83, pd.get_payment_value(pi))
        pi.task_id = "bbb"
        pd.add_payment(pi)
        self.assertEquals(10.30, pd.get_payment_value(pi))
        pi.task_id = "xyz"
        self.assertEquals(40.83, pd.get_payment_value(pi))

        # test change state
        pi3 = deepcopy(pi)
        pi3.task_id = "bbb"
        pi4 = deepcopy(pi)
        pi4.computer.key_id = "GHI"
        with self.assertLogs(logger, level=1) as l:
            self.assertIsNone(pd.get_state(pi4))
        pd.add_payment(pi3)
        pd.add_payment(pi4)
        self.assertTrue(any(["not exist" in log for log in l.output]))
        self.assertEquals(pd.get_state(pi), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi2), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi3), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi4), PaymentState.waiting_for_task_to_finish)
        pd.change_state(pi.task_id, "XXXXX31")
        self.assertEquals(pd.get_state(pi), "XXXXX31")
        self.assertEquals(pd.get_state(pi2), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi3), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi4), "XXXXX31")
        pd.change_state(pi.task_id, PaymentState.waiting_to_be_paid)
        self.assertEquals(pd.get_state(pi), PaymentState.waiting_to_be_paid)
        self.assertEquals(pd.get_state(pi2), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi3), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi4), PaymentState.waiting_to_be_paid)
        pd.change_state(pi2.task_id, PaymentState.settled)
        self.assertEquals(pd.get_state(pi), PaymentState.waiting_to_be_paid)
        self.assertEquals(pd.get_state(pi2), PaymentState.settled)
        self.assertEquals(pd.get_state(pi3), PaymentState.waiting_for_task_to_finish)
        self.assertEquals(pd.get_state(pi3), PaymentState.waiting_for_task_to_finish)

        # test newest payments
        res = [p for p in pd.get_newest_payment(2)]
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].task, pi2.task_id)
        self.assertEqual(res[0].to_node_id, pi2.computer.key_id)
        self.assertEqual(res[1].task, pi.task_id)

        for i in range(10, 0, -1):
            pi.task_id = "xyz{}".format(i)
            pd.add_payment(pi)
        res = [p for p in pd.get_newest_payment(3)]
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0].task, "xyz1")
        self.assertEqual(res[1].task, "xyz2")
        self.assertEqual(res[2].task, "xyz3")
        for i in range(11, 20):
            pi.task_id = "xyz{}".format(i)
            pd.add_payment(pi)
        res = [p for p in pd.get_newest_payment(3)]
        self.assertEqual(res[0].task, "xyz19")
        self.assertEqual(res[1].task, "xyz18")
        self.assertEqual(res[2].task, "xyz17")


class TestPaymentsKeeper(TestWithDatabase):
    def test_init(self):
        pk = PaymentsKeeper("ABC")
        self.assertIsInstance(pk, PaymentsKeeper)

    def test_task_finished(self):
        pk = PaymentsKeeper("ABC")
        pk.task_finished("xyz")
        self.assertEqual(pk.finished_tasks[len(pk.finished_tasks) - 1], "xyz")
        pk.task_finished("zyx")
        self.assertEqual(pk.finished_tasks[len(pk.finished_tasks) - 1], "zyx")
        self.assertEqual(pk.finished_tasks[0], "xyz")

    def test_database(self):
        pk = PaymentsKeeper("ABC")
        self.database.check_node("ABC")
        ai = AccountInfo("DEF", 20400, "10.0.0.1", "node1", "node_info")
        pi = PaymentInfo("xyz", "xxyyzz", 20.23, ai)
        pk.finished_subtasks(pi)
        pi.subtask_id = "aabbcc"
        pk.finished_subtasks(pi)
        pi2 = deepcopy(pi)
        pi2.task_id = "xxx"
        pk.finished_subtasks(pi2)
        pi3 = deepcopy(pi)
        pi3.value = 10
        pi3.computer.key_id = "GHI"
        pk.finished_subtasks(pi3)
        pi3.subtask_id = "xxxxxxx"
        pk.finished_subtasks(pi3)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 3)
        self.assertEqual(all_payments[0]["task"], "xyz")
        self.assertEqual(all_payments[0]["node"], "GHI")
        self.assertEqual(all_payments[0]["value"], 20)
        self.assertEqual(all_payments[0]["state"], PaymentState.waiting_for_task_to_finish)
        self.assertEqual(all_payments[1]["task"], "xxx")
        self.assertEqual(all_payments[1]["node"], "DEF")
        self.assertEqual(all_payments[1]["value"], 20.23)
        self.assertEqual(all_payments[1]["state"], PaymentState.waiting_for_task_to_finish)
        self.assertEqual(all_payments[2]["task"], "xyz")
        self.assertEqual(all_payments[2]["node"], "DEF")
        self.assertEqual(all_payments[2]["value"], 40.46)
        self.assertEqual(all_payments[2]["state"], PaymentState.waiting_for_task_to_finish)
        pk.task_finished("xyz")
        pk.finished_subtasks(pi3)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 3)

        xyzCalled = False
        for payment in all_payments:
            if payment["task"] == "xyz":
                self.assertEqual(payment["state"], PaymentState.waiting_to_be_paid)
                xyzCalled = True
            else:
                self.assertEqual(payment["state"], PaymentState.waiting_for_task_to_finish)
        self.assertTrue(xyzCalled)

        t, list = pk.get_new_payments_task(1000)
        self.assertIsNotNone(t)
        self.assertIsNotNone(list)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 3)
        xyzCalled = False
        for payment in all_payments:
            if payment["task"] == "xyz":
                self.assertEqual(payment["state"], PaymentState.settled)
                xyzCalled = True
            else:
                self.assertEqual(payment["state"], PaymentState.waiting_for_task_to_finish)
        self.assertTrue(xyzCalled)

        pk.payment_failure("xyz")
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 3)
        xyzCalled = False
        for payment in all_payments:
            if payment["task"] == "xyz":
                self.assertEqual(payment["state"], PaymentState.waiting_to_be_paid)
                xyzCalled = True
            else:
                self.assertEqual(payment["state"], PaymentState.waiting_for_task_to_finish)
        self.assertTrue(xyzCalled)


class TestAccountInfo(unittest.TestCase):
    def test_comparison(self):
        k = EllipticalKeysAuth()
        a = AccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", Node())
        b = AccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", Node())
        self.assertEqual(a, b)
        n = Node(prv_addr="10.10.10.10", prv_port=1031, pub_addr="10.10.10.10", pub_port=1032)
        c = AccountInfo(k.get_key_id(), 5112, "10.0.0.2", "test-test2-test", n)
        self.assertEqual(a, c)
        k.generate_new(2)
        c.key_id = k.get_key_id()
        self.assertNotEqual(a, c)
