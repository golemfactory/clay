import mock
from mock import patch, MagicMock

from ethereum.keys import PBKDF2_CONSTANTS

from golem import testutils
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import (
    EthereumTransactionSystem
)

PBKDF2_CONSTANTS['c'] = 10  # Limit KDF difficulty.


class TestEthereumTransactionSystem(TestWithDatabase, LogTestCase,
                                    testutils.PEP8MixIn):
    PEP8_FILES = ['golem/transactions/ethereum/ethereumtransactionsystem.py', ]

    def test_init(self):
        e = EthereumTransactionSystem(self.tempdir, 'password')
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str

    def test_invalid_account_password(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "")

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, 'password')
        assert e.get_balance() == (None, None, None)

    @patch('golem.ethereum.paymentprocessor.PaymentProcessor.start')
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.sleep')
    def test_sync(self, sleep, *_):
        switch_value = [True]

        def false():
            return False

        def switch(*_):
            switch_value[0] = not switch_value[0]
            return not switch_value[0]

        def error(*_):
            raise Exception

        e = EthereumTransactionSystem(self.tempdir, 'password')

        sleep.call_count = 0
        with patch(
                'golem.ethereum.paymentprocessor.PaymentProcessor.is_synchronized',
                side_effect=false):
            e.sync()
            assert sleep.call_count == 1

        sleep.call_count = 0
        with patch(
                'golem.ethereum.paymentprocessor.PaymentProcessor.is_synchronized',
                side_effect=switch):
            e.sync()
            assert sleep.call_count == 2

        sleep.call_count = 0
        with patch(
                'golem.ethereum.paymentprocessor.PaymentProcessor.is_synchronized',
                side_effect=error):
            e.sync()
            assert sleep.call_count == 0

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None)

    @mock.patch('golem.transactions.service.Service.running',
                new_callable=mock.PropertyMock)
    def test_stop(self, mock_is_service_running):
        pkg = 'golem.ethereum.'

        def init(self, datadir):
            self.rpcport = 65001
            self._NodeProcess__ps = None
            self.web3 = MagicMock()
            self.datadir = datadir

        with patch('twisted.internet.task.LoopingCall.start'), \
            patch('twisted.internet.task.LoopingCall.stop'), \
            patch(pkg + 'node.NodeProcess.start'), \
            patch(pkg + 'node.NodeProcess.stop'), \
            patch(pkg + 'node.NodeProcess.__init__', _init), \
            patch('web3.providers.rpc.HTTPProvider.__init__', _init):

            e = EthereumTransactionSystem(self.tempdir, 'password')

            assert e._EthereumTransactionSystem__proc.start.called
            assert e._EthereumTransactionSystem__eth_node.node.start.called

            mock_is_service_running.return_value = False
            e.stop()
            assert not e.incomes_keeper.processor. \
                _PaymentProcessor__client.node.stop.called
            assert not e.incomes_keeper.processor. \
                _loopingCall.stop.called

            mock_is_service_running.return_value = True
            e.stop()
            assert e.incomes_keeper.processor. \
                _PaymentProcessor__client.node is None
            assert e.incomes_keeper.processor. \
                _loopingCall.stop.called
