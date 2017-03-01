
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
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    def test_wrong_address_in_pay_for_task(self):
        addr = keys.privtoaddr(PRIV_KEY)
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_payment_address() == '0x' + addr.encode('hex')
        e.pay_for_task("xyz", [])

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None)
