from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.transactionsystem import TransactionSystem
from golem.transactions.paymentskeeper import AccountInfo
from golem.network.p2p.node import Node


class TestTransactionSystem(TestWithDatabase):
    def test_init(self):
        e = TransactionSystem("ABC")
        self.assertIsInstance(e, TransactionSystem)

    def test_add_payment_info(self):
        e = TransactionSystem("ABC")
        ai = AccountInfo("DEF", 2010, "10.0.0.1", "node1", Node())
        e.add_payment_info("xyz", "xxyyzz", 10, ai)

    def test_pay_for_task(self):
        e = TransactionSystem("ABC")
        with self.assertRaises(NotImplementedError):
            e.pay_for_task("xyz", [])
