from mock import patch

from ethereum import keys

from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem

PRIV_KEY = '\7' * 32


class TestEthereumTransactionSystem(TestWithDatabase):
    def test_init(self):
        e = EthereumTransactionSystem("ABC", PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert e.get_eth_account()

    def test_invalid_private_key(self):
        with self.assertRaises(AssertionError):
            EthereumTransactionSystem("ABC", "not a private key")

    @patch("golem.transactions.ethereum.ethereumtransactionsystem.EthereumConnector")
    def test_wrong_address_in_global_pay_for_task(self, mock_connector):
        addr = keys.privtoaddr(PRIV_KEY)
        e = EthereumTransactionSystem("ABC", PRIV_KEY)
        assert e.get_eth_account()
        assert e.eth_account
        assert e.eth_account.get_str_addr()
        e.global_pay_for_task("xyz", [])
        addr_str = '0x' + addr.encode('hex')
        mock_connector.return_value.pay_for_task.assert_called_with(addr_str, "xyz", [])
