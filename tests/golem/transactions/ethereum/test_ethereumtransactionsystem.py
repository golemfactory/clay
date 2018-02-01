import mock
from mock import patch, MagicMock

from golem import testutils
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import (
    EthereumTransactionSystem
)

PRIV_KEY = '07' * 32


class TestEthereumTransactionSystem(TestWithDatabase, LogTestCase,
                                    testutils.PEP8MixIn):
    PEP8_FILES = ['golem/transactions/ethereum/ethereumtransactionsystem.py', ]

    def test_init(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        self.assertIsInstance(e, EthereumTransactionSystem)
        assert type(e.get_payment_address()) is str
        e.stop()

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    @mock.patch(
        'golem.transactions.ethereum.ethereumtransactionsystem.'
        'EthereumTransactionSystem.get_payment_address',
        new_callable=mock.PropertyMock)
    def test_invalid_eth_adress_construction(self, mock_get_payment_address):
        mock_get_payment_address().return_value = None

        with self.assertRaisesRegexp(ValueError,
                                     "Invalid Ethereum address constructed"):
            EthereumTransactionSystem(self.tempdir, PRIV_KEY)

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None)
        e.stop()

    @mock.patch('golem.core.service.LoopingCallService.running',
                new_callable=mock.PropertyMock)
    def test_stop(self, mock_is_service_running):
        pkg = 'golem.ethereum.'

        def _init(self, *args, **kwargs):
            self.rpcport = 65001
            self._NodeProcess__ps = None
            self.web3 = MagicMock()

        with patch('twisted.internet.task.LoopingCall.start'), \
            patch('twisted.internet.task.LoopingCall.stop'), \
            patch('golem_sci.new_testnet'), \
            patch(pkg + 'node.NodeProcess.start'), \
            patch(pkg + 'node.NodeProcess.stop'), \
            patch(pkg + 'node.NodeProcess.__init__', _init), \
            patch('web3.providers.rpc.HTTPProvider.__init__', _init):

            mock_is_service_running.return_value = False
            e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
            assert e.payment_processor._loopingCall.start.called
            assert e._node.start.called

            mock_is_service_running.return_value = False
            e.stop()
            assert e._node.stop.called
            assert not e.payment_processor._loopingCall.stop.called

            mock_is_service_running.return_value = True
            e.stop()
            assert e.payment_processor._loopingCall.stop.called
