import unittest.mock as mock

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
        assert isinstance(e.get_payment_address(), str)
        e.stop()

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None, None, None)
        e.stop()

    @mock.patch('golem.core.service.LoopingCallService.running',
                new_callable=mock.PropertyMock)
    def test_stop(self, mock_is_service_running):
        pkg = 'golem.ethereum.'

        def _init(self, *args, **kwargs):
            self.rpcport = 65001
            self._NodeProcess__ps = None
            self.web3 = mock.MagicMock()

        with mock.patch('twisted.internet.task.LoopingCall.start'), \
                mock.patch('twisted.internet.task.LoopingCall.stop'), \
                mock.patch('golem_sci.new_sci'), \
                mock.patch(pkg + 'node.NodeProcess.start'), \
                mock.patch(pkg + 'node.NodeProcess.stop'), \
                mock.patch(pkg + 'node.NodeProcess.__init__', _init), \
                mock.patch('web3.providers.rpc.HTTPProvider.__init__', _init):

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
