import unittest

from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo, EthereumPaymentsKeeper
from golem.transactions.transactionsystem import PaymentInfo
from golem.core.keysauth import EllipticalKeysAuth
from golem.tools.testwithdatabase import TestWithDatabase
from golem.network.p2p.node import Node


class TestEthereumPaymentsKeeper(TestWithDatabase):
    def test_get_list_of_payment(self):
        e = EthereumPaymentsKeeper("ABC")
        self.database.check_node("ABC")

        addr1 = "0x09197b95a57ad20ee68b53e0843fb1d218db6a78"
        ai = EthAccountInfo("DEF", 20400, "10.0.0.1", "node1", Node(), addr1)

        addr2 = "0x7b82fd1672b8020415d269c53cd1a2230fde9386"
        ai2 = EthAccountInfo("DEF", 20400, "10.0.0.1", "node1", Node(), addr2)

        pi = PaymentInfo("x-y-z", "xx-yy-zz", 19.26, ai)

        pi2 = PaymentInfo("a-b-c", "xx-yy-zz", 10.14, ai)
        e.finished_subtasks(pi)
        e.finished_subtasks(pi2)

        pi.subtask_id = "aa-bb-cc"

        e.finished_subtasks(pi)
        pi.computer = ai2
        pi.subtask_id = 'subtask3'
        e.finished_subtasks(pi)

        pi2.computer = ai2
        pi2.subtask_id = "subtask2"
        e.finished_subtasks(pi2)
        pi2.subtask_id = "subtask3"
        e.finished_subtasks(pi2)

        pi.computer = ai
        pi.subtask_id = "qw12wuo131uaoa"
        e.finished_subtasks(pi)
        payments = e.get_list_of_payments(e.computing_tasks["x-y-z"])
        self.assertEqual(len(payments), 2)
        payments[addr1].value = 19.26 * 3
        payments[addr2].vaue = 19.26
        payments2 = e.get_list_of_payments(e.computing_tasks["a-b-c"])
        self.assertEqual(len(payments2), 2)
        payments[addr1].value = 10.14
        payments[addr2].vaue = 10.14 * 2





class TestEthAccountInfo(unittest.TestCase):
    def test_comparison(self):
        k = EllipticalKeysAuth()
        addr1 = "0x09197b95a57ad20ee68b53e0843fb1d218db6a78"
        a = EthAccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", Node(), addr1)
        b = EthAccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", Node(), addr1)
        self.assertEqual(a, b)
        n = Node(prv_addr="10.10.10.10", prv_port=1031, pub_addr="10.10.10.10", pub_port=1032)
        c = EthAccountInfo(k.get_key_id(), 5111, "10.0.0.1", "test-test-test", n, addr1)
        self.assertEqual(a, c)
        k.generate_new(2)
        c.key_id = k.get_key_id()
        self.assertNotEqual(a, c)
        addr2 = "0x7b82fd1672b8020415d269c53cd1a2230fde9386"
        b.eth_account = addr2
        self.assertNotEqual(a, b)
        a.eth_account = addr2
        self.assertEqual(a, b)
