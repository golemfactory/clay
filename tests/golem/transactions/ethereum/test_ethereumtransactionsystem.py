from os import urandom

from ethereum import keys

from golem.network.p2p.node import Node
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem

PRIV_KEY = '\7' * 32


class TestEthereumTransactionSystem(TestWithDatabase):
    def test_init(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str

    def test_invalid_private_key(self):
        with self.assertRaises(AssertionError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    def test_wrong_address_in_pay_for_task(self):
        addr = keys.privtoaddr(PRIV_KEY)
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_payment_address() == '0x' + addr.encode('hex')
        e.pay_for_task("xyz", [])

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (0, 0, 0)

    def test_get_payment_for_subtasks(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_payment_for_subtasks(["NOTEXISTING", "NOTEXISITNG2"]) == 0
        ai = EthAccountInfo("NODE 1", 2010, "10.0.0.1", "node1", Node(), urandom(20))
        e.add_payment_info("TASK1", "SUBTASK1", 10341, ai)
        e.add_payment_info("TASK1", "SUBTASK2", 255, ai)
        e.add_payment_info("TASK1", "SUBTASK3", 200000, ai)
        assert e.get_payment_for_subtasks(["SUBTASK3", "SUBTASK1", "SUBTASK2"]) == 210596