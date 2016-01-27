import unittest

from rlp.utils import decode_hex
from sha3 import sha3_256

from golem.transactions.ethereum.ethereumpaymentskeeper import (EthAccountInfo, EthereumPaymentsKeeper, EthereumAddress,
                                                                logger)
from golem.transactions.transactionsystem import PaymentInfo
from golem.core.keysauth import EllipticalKeysAuth
from golem.tools.assertlogs import LogTestCase
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


class TestEthereumAddress(LogTestCase):
    def test_init(self):
        addr1 = "0x7b82fd1672b8020415d269c53cd1a2230fde9386"
        e = EthereumAddress(addr1)
        self.assertEqual(addr1, e.get_str_addr())

        addr2 = addr1.upper()
        e2 = EthereumAddress(addr2)
        self.assertEqual(addr1, e2.get_str_addr())
        addr3 = "0x0121121"
        with self.assertLogs(logger, level=1) as l:
            e = EthereumAddress(addr3)
        self.assertTrue(any(["Can't" in log for log in l.output]))
        self.assertIsNone(e.address)
        # We may think about allowing to add address in such formats in the future
        addr4 = bin(int(addr1, 16))[2:].zfill(160)
        with self.assertLogs(logger, level=1) as l:
            e = EthereumAddress(addr4)
        self.assertTrue(any(["Can't" in log for log in l.output]))
        self.assertIsNone(e.address)
        addr5 = decode_hex(addr1[2:])
        e = EthereumAddress(addr5)
        self.assertTrue(addr1, e.get_str_addr())
        e = EthereumAddress(addr5 + sha3_256(addr5).digest()[:4])
        self.assertTrue(addr1, e.get_str_addr())
        addr6 = ""
        e = EthereumAddress(addr6)
        self.assertIsNone(e.get_str_addr())
