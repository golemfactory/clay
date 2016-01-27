from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.transactionsystem import TransactionSystem


class TestTransactionSystem(TestWithDatabase):
    def test_init(self):
        with self.assertRaises(Exception):
            TransactionSystem("ABC")
        self.database.check_node("ABC")
        e = TransactionSystem("ABC")
        self.assertIsInstance(e, TransactionSystem)
