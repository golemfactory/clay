from mock import patch

from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.assertlogs import LogTestCase
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem, logger


class TestEthereumTransactionSystem(TestWithDatabase, LogTestCase):
    def test_init(self):
        e = EthereumTransactionSystem("ABC", "0x0")
        self.assertIsInstance(e, EthereumTransactionSystem)
        self.assertIsNone(e.get_eth_account())

    @patch("golem.transactions.ethereum.ethereumtransactionsystem.EthereumConnector")
    def test_wrong_address_in_global_pay_for_task(self, mock_connector):
        e = EthereumTransactionSystem("ABC", "0x0")
        with self.assertLogs(logger, level=1) as l:
            e.global_pay_for_task("xyz", [])
        self.assertTrue(any(["Can't" in log for log in l.output]))
        mock_connector.return_value.pay_for_task.assert_not_called()
        addr = "0x09197b95a57ad20ee68b53e0843fb1d218db6a78"
        e = EthereumTransactionSystem("ABC", addr)
        self.assertIsNotNone(e.get_eth_account())
        e.global_pay_for_task("xyz", [])
        mock_connector.return_value.pay_for_task.assert_called_with(addr, "xyz", [])




