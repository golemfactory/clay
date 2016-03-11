from ethereum import keys

from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem

PRIV_KEY = '\7' * 32


class TestEthereumTransactionSystem(TestWithDatabase):
    def test_init(self):
        e = EthereumTransactionSystem("ABC", PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str

    def test_invalid_private_key(self):
        with self.assertRaises(AssertionError):
            EthereumTransactionSystem("ABC", "not a private key")

    def test_wrong_address_in_global_pay_for_task(self):
        addr = keys.privtoaddr(PRIV_KEY)
        e = EthereumTransactionSystem("ABC", PRIV_KEY)
        assert e.get_payment_address() == '0x' + addr.encode('hex')
        e.global_pay_for_task("xyz", [])
