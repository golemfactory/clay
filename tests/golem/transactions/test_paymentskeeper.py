from copy import deepcopy
from peewee import IntegrityError
from os import urandom

from golem.network.p2p.node import Node
from golem.core.keysauth import EllipticalKeysAuth
from golem.model import PaymentStatus
from golem.testutils import TempDirFixture
from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.assertlogs import LogTestCase
from golem.transactions.paymentskeeper import PaymentsDatabase, PaymentInfo, logger, \
    PaymentsKeeper
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo


class TestPaymentsDatabase(LogTestCase, TestWithDatabase):

    def test_init(self):
        pd = PaymentsDatabase()
        self.assertIsInstance(pd, PaymentsDatabase)

    def test_payments(self):
        pd = PaymentsDatabase()

        # test get payments
        addr = urandom(20)
        ai = EthAccountInfo("DEF", 20400, "10.0.0.1", "node1", "info", addr)
        pi = PaymentInfo("xyz", "xxyyzz", 20, ai)
        with self.assertLogs(logger, level=1) as l:
            self.assertEquals(0, pd.get_payment_value(pi))
        self.assertTrue(any("not exist" in log for log in l.output))
        pd.add_payment(pi)
        self.assertEquals(20, pd.get_payment_value(pi))
        pi = PaymentInfo("xyz", "aabbcc", 10, ai)
        self.assertEquals(0, pd.get_payment_value(pi))
        pi2 = PaymentInfo("zzz", "xxyyxx", 14, ai)
        pd.add_payment(pi2)
        self.assertEquals(14, pd.get_payment_value(pi2))
        self.assertEquals(0, pd.get_payment_value(pi))

        # test add_payment
        pd.add_payment(pi)
        self.assertEquals(pi.value, pd.get_payment_value(pi))
        self.assertRaises(IntegrityError, lambda: pd.add_payment(pi))
        self.assertEquals(pi.value, pd.get_payment_value(pi))
        pi.subtask_id = "bbb"
        pd.add_payment(pi)
        self.assertEquals(10, pd.get_payment_value(pi))
        pi.subtask_id = "xyz"
        self.assertEquals(0, pd.get_payment_value(pi))

        # test change state
        pi3 = deepcopy(pi)
        pi3.subtask_id = "bbbxxx"
        pi4 = deepcopy(pi)
        pi4.computer.eth_account.address = "GHI"
        pi4.subtask_id = "ghighi"
        with self.assertLogs(logger, level=1) as l:
            self.assertIsNone(pd.get_state(pi4))
        pd.add_payment(pi3)
        pd.add_payment(pi4)
        self.assertTrue(any("not exist" in log for log in l.output))
        self.assertEquals(pd.get_state(pi), None)
        self.assertEquals(pd.get_state(pi2), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi3), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi4), PaymentStatus.awaiting)
        pd.change_state(pi4.subtask_id, PaymentStatus.sent)
        self.assertEquals(pd.get_state(pi), None)
        self.assertEquals(pd.get_state(pi2), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi3), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi4), PaymentStatus.sent)
        pd.change_state(pi4.subtask_id, PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi), None)
        self.assertEquals(pd.get_state(pi2), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi3), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi4), PaymentStatus.awaiting)
        pd.change_state(pi2.subtask_id, PaymentStatus.confirmed)
        self.assertEquals(pd.get_state(pi), None)
        self.assertEquals(pd.get_state(pi2), PaymentStatus.confirmed)
        self.assertEquals(pd.get_state(pi3), PaymentStatus.awaiting)
        self.assertEquals(pd.get_state(pi3), PaymentStatus.awaiting)

        # test newest payments
        res = [p for p in pd.get_newest_payment(2)]
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].subtask, pi2.subtask_id)
        self.assertEqual(res[0].payee, pi2.computer.eth_account.address)
        self.assertEqual(res[1].subtask, pi4.subtask_id)

        for i in range(10, 0, -1):
            pi.subtask_id = "xyz{}".format(i)
            pd.add_payment(pi)
        res = [p for p in pd.get_newest_payment(3)]
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0].subtask, "xyz1")
        self.assertEqual(res[1].subtask, "xyz2")
        self.assertEqual(res[2].subtask, "xyz3")
        for i in range(11, 20):
            pi.subtask_id = "xyz{}".format(i)
            pd.add_payment(pi)
        res = [p for p in pd.get_newest_payment(3)]
        self.assertEqual(res[0].subtask, "xyz19")
        self.assertEqual(res[1].subtask, "xyz18")
        self.assertEqual(res[2].subtask, "xyz17")


class TestPaymentsKeeper(TestWithDatabase):
    def test_init(self):
        pk = PaymentsKeeper()
        self.assertIsInstance(pk, PaymentsKeeper)

    def test_database(self):
        pk = PaymentsKeeper()
        addr = urandom(20)
        addr2 = urandom(20)
        ai = EthAccountInfo("DEF", 20400, "10.0.0.1", "1", "i", addr2)
        pi = PaymentInfo("xyz", "xxyyzz", 2023, ai)
        pk.finished_subtasks(pi)
        pi.subtask_id = "aabbcc"
        pk.finished_subtasks(pi)
        pi2 = deepcopy(pi)
        pi2.subtask_id = "xxxyyy"
        pk.finished_subtasks(pi2)
        pi3 = deepcopy(pi)
        pi3.value = 10
        pi3.computer.eth_account.address = addr
        pi3.subtask_id = "zzzzzz"
        pk.finished_subtasks(pi3)
        pi3.subtask_id = "xxxxxx"
        pk.finished_subtasks(pi3)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 5)
        self.assertEqual(all_payments[0]["subtask"], "xxxxxx")
        self.assertEqual(all_payments[0]["payee"], addr)
        self.assertEqual(all_payments[0]["value"], 10)
        self.assertEqual(all_payments[0]["status"], PaymentStatus.awaiting.value)
        self.assertEqual(all_payments[1]["subtask"], "zzzzzz")
        self.assertEqual(all_payments[1]["payee"], addr)
        self.assertEqual(all_payments[1]["value"], 10)
        self.assertEqual(all_payments[1]["status"], PaymentStatus.awaiting.value)
        self.assertEqual(all_payments[2]["subtask"], "xxxyyy")
        self.assertEqual(all_payments[2]["payee"], addr2)
        self.assertEqual(all_payments[2]["value"], 2023)
        self.assertEqual(all_payments[2]["status"], PaymentStatus.awaiting.value)
        pi3.subtask_id = "whaooa!"
        pk.finished_subtasks(pi3)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 6)
        assert pk.get_payment("xxyyzz") == 2023
        assert pk.get_payment("not existing") == 0


class TestAccountInfo(TempDirFixture):
    def test_comparison(self):
        k = EllipticalKeysAuth(self.path)
        e = urandom(20)
        a = EthAccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", Node(), e)
        b = EthAccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", Node(), e)
        self.assertEqual(a, b)
        n = Node(prv_addr="10.10.10.10", prv_port=1031, pub_addr="10.10.10.10", pub_port=1032)
        c = EthAccountInfo(k.get_key_id(), 5112, "10.0.0.2", "test-test2-test", n, e)
        self.assertEqual(a, c)
        k.generate_new(2)
        c.key_id = k.get_key_id()
        self.assertNotEqual(a, c)
