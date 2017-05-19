from ethereum import keys
from mock import patch

from golem import testutils
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import EthereumTransactionSystem

PRIV_KEY = '\7' * 32


class TestEthereumTransactionSystem(TestWithDatabase, LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/transactions/ethereum/ethereumtransactionsystem.py', ]

    def test_init(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None)

    @patch('golem.ethereum.paymentprocessor.PaymentProcessor.start')
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.sleep')
    def test_sync(self, sleep, *_):

        switch_value = [True]

        def switch(*_):
            switch_value[0] = not switch_value[0]
            return not switch_value[0]

        def error(*_):
            raise Exception

        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

        sleep.call_count = 0
        with patch('golem.ethereum.Client.is_syncing', side_effect=lambda: False):
            e.sync()
            assert sleep.call_count == 1

        sleep.call_count = 0
        with patch('golem.ethereum.Client.is_syncing', side_effect=switch):
            e.sync()
            assert sleep.call_count == 2

        sleep.call_count = 0
        with patch('golem.ethereum.Client.is_syncing', side_effect=error):
            e.sync()
            assert sleep.call_count == 0

    def test_stop(self):

        pkg = 'golem.ethereum.'

        def init(self, *args, **kwargs):
            self.rpcport = 65001
            self._NodeProcess__ps = None
            self.testnet = True

        with patch(pkg + 'paymentprocessor.PaymentProcessor.start'), \
            patch(pkg + 'paymentprocessor.PaymentProcessor.stop'), \
            patch(pkg + 'node.NodeProcess.start'), \
            patch(pkg + 'node.NodeProcess.stop'), \
            patch(pkg + 'node.NodeProcess.__init__', init), \
            patch(pkg + 'node.NodeProcess.system_geth', False, create=True), \
            patch('web3.providers.rpc.HTTPProvider.__init__', init):

            e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

            assert e._EthereumTransactionSystem__proc.start.called
            assert e._EthereumTransactionSystem__eth_node.node.start.called

            e.stop()

            assert not e._EthereumTransactionSystem__proc.stop.called
            assert e._EthereumTransactionSystem__eth_node.node.stop.called

            e._EthereumTransactionSystem__eth_node.node.stop.called = False
            e._EthereumTransactionSystem__proc._loopingCall.running = True

            e.stop()

            assert e._EthereumTransactionSystem__proc.stop.called
            assert e._EthereumTransactionSystem__eth_node.node.stop.called
