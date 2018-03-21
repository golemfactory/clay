from unittest.mock import patch, Mock, ANY, PropertyMock

import golem_sci

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

    @patch('golem.core.service.LoopingCallService.running',
           new_callable=PropertyMock)
    def test_stop(self, mock_is_service_running):
        pkg = 'golem.ethereum.'
        new_sci_method_name = \
            'golem.transactions.ethereum.ethereumtransactionsystem.new_sci'

        def _init(self, *args, **kwargs):
            self.rpcport = 65001
            self._NodeProcess__ps = None
            self.web3 = Mock()

        with patch('twisted.internet.task.LoopingCall.start'), \
                patch('twisted.internet.task.LoopingCall.stop'), \
                patch(new_sci_method_name), \
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

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.NodeProcess',
           Mock())
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.new_sci')
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.'
           'PaymentProcessor')
    def test_mainnet_flag(self, pp, new_sci):
        EthereumTransactionSystem(self.tempdir, PRIV_KEY, False)
        new_sci.assert_called_once_with(
            ANY,
            ANY,
            ANY,
            golem_sci.chains.RINKEBY,
        )
        pp.assert_called_once_with(sci=ANY, faucet=True)

        new_sci.reset_mock()
        pp.reset_mock()

        EthereumTransactionSystem(self.tempdir, PRIV_KEY, True)
        new_sci.assert_called_once_with(
            ANY,
            ANY,
            ANY,
            golem_sci.chains.MAINNET,
        )
        pp.assert_called_once_with(sci=ANY, faucet=False)
