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
        price_mod = 10
        price = e.add_payment_info("xyz", "xxyyzz", price_mod, ai)
        self.assertEqual(price, price_mod * e.price_base)