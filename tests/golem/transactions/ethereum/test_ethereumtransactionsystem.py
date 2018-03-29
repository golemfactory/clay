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

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.NodeProcess',
           Mock())
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.new_sci')
    def test_withdraw(self, new_sci):
        sci = Mock()
        sci.GAS_PRICE = 0
        sci.GAS_PER_PAYMENT = 0
        sci.GAS_BATCH_PAYMENT_BASE = 0
        new_sci.return_value = sci
        eth_balance = 400
        gnt_balance = 100
        gntb_balance = 200
        sci.get_eth_balance.return_value = eth_balance
        sci.get_gnt_balance.return_value = gnt_balance
        sci.get_gntb_balance.return_value = gntb_balance
        eth_tx = '0xee'
        gnt_tx = '0xbad'
        gntb_tx = '0xfad'
        sci.transfer_eth.return_value = eth_tx
        sci.transfer_gnt.return_value = gnt_tx
        sci.convert_gntb_to_gnt.return_value = gntb_tx
        destination = '0xdead'

        ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

        # Unknown currency
        with self.assertRaises(ValueError):
            ets.withdraw(1, destination, 'asd')

        # Not enough GNT
        with self.assertRaises(ValueError):
            ets.withdraw(gnt_balance + gntb_balance + 1, destination, 'GNT')

        # Not enough ETH
        with self.assertRaises(ValueError):
            ets.withdraw(eth_balance + 1, destination, 'ETH')

        # Enough GNT
        res = ets.withdraw(gnt_balance - 1, destination, 'GNT')
        assert res == [gnt_tx]
        sci.transfer_gnt.assert_called_once_with(destination, gnt_balance - 1)
        sci.reset_mock()

        # Enough GNTB
        res = ets.withdraw(gntb_balance - 1, destination, 'GNT')
        assert res == [gntb_tx]
        sci.convert_gntb_to_gnt.assert_called_once_with(
            destination,
            gntb_balance - 1,
        )
        sci.reset_mock()

        # Enough total GNT
        res = ets.withdraw(gnt_balance + gntb_balance - 1, destination, 'GNT')
        assert res == [gnt_tx, gntb_tx]
        sci.transfer_gnt.assert_called_once_with(destination, gnt_balance)
        sci.convert_gntb_to_gnt.assert_called_once_with(
            destination,
            gntb_balance - 1,
        )
        sci.reset_mock()

        # Enough ETH
        res = ets.withdraw(eth_balance - 1, destination, 'ETH')
        assert res == [eth_tx]
        sci.transfer_eth.assert_called_once_with(destination, eth_balance - 1)
        sci.reset_mock()

        # Enough ETH with lock
        res = ets.withdraw(eth_balance - 3, destination, 'ETH', 2)
        assert res == [eth_tx]
        sci.transfer_eth.assert_called_once_with(destination, eth_balance - 3)
        sci.reset_mock()

        # Not enough ETH with lock
        with self.assertRaises(ValueError):
            ets.withdraw(eth_balance - 3, destination, 'ETH', 4)
        sci.reset_mock()

        # Enough GNT with lock
        res = ets.withdraw(gnt_balance + gntb_balance - 1, destination, 'GNT',
                           1)
        assert res == [gnt_tx, gntb_tx]
        sci.transfer_gnt.assert_called_once_with(destination, gnt_balance)
        sci.convert_gntb_to_gnt.assert_called_once_with(
            destination,
            gntb_balance - 1,
        )
        sci.reset_mock()

        # Not enough GNT with lock
        with self.assertRaises(ValueError):
            ets.withdraw(gnt_balance + gntb_balance - 1, destination, 'GNT', 2)
        sci.reset_mock()
