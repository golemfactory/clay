from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem


class TestEthereumTransactionSystem(TestWithDatabase):
    def test_init(self):
        with self.assertRaises(Exception):
            EthereumTransactionSystem("ABC", "0x0")
        self.database.check_node("ABC")
        e = EthereumTransactionSystem("ABC", "0x0")
        self.assertIsInstance(e, EthereumTransactionSystem)
