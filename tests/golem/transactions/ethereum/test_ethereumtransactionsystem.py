from os import urandom
import unittest
from unittest.mock import patch, Mock, ANY, PropertyMock

from eth_utils import encode_hex
import golem_sci
import requests

from golem import testutils
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumtransactionsystem import (
    EthereumTransactionSystem,
    tETH_faucet_donate,
)
from golem.transactions.ethereum.exceptions import NotEnoughFunds

PRIV_KEY = '07' * 32


class TestEthereumTransactionSystem(TestWithDatabase, LogTestCase,
                                    testutils.PEP8MixIn):
    PEP8_FILES = ['golem/transactions/ethereum/ethereumtransactionsystem.py', ]

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    def test_get_balance(self):
        e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        assert e.get_balance() == (None, None, None, None, None)

    @patch('golem.core.service.LoopingCallService.running',
           new_callable=PropertyMock)
    def test_stop(self, mock_is_service_running):
        with patch('twisted.internet.task.LoopingCall.start'), \
                patch('twisted.internet.task.LoopingCall.stop'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'new_sci'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'GNTConverter'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'PaymentProcessor'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'NodeProcess'):

            mock_is_service_running.return_value = False
            e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
            e._node.start.assert_called_once_with(None)  # noqa pylint:disable=no-member
            e.start()

            mock_is_service_running.return_value = True
            e.stop()
            e._node.stop.assert_called_once_with()  # pylint:disable=no-member
            e.payment_processor.sendout.assert_called_once_with(0)  # noqa pylint:disable=no-member

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.NodeProcess',
           Mock())
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.GNTConverter',
           Mock())
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.new_sci')
    def test_mainnet_flag(self, new_sci):

        with patch('golem.transactions.ethereum.ethereumtransactionsystem'
                   '.ETHEREUM_CHAIN', 'rinkeby'):
            EthereumTransactionSystem(self.tempdir, PRIV_KEY)
            new_sci.assert_called_once_with(
                ANY,
                ANY,
                ANY,
                ANY,
                golem_sci.chains.RINKEBY,
            )

        new_sci.reset_mock()

        with patch('golem.transactions.ethereum.ethereumtransactionsystem'
                   '.ETHEREUM_CHAIN', 'mainnet'):
            EthereumTransactionSystem(self.tempdir, PRIV_KEY)
            new_sci.assert_called_once_with(
                ANY,
                ANY,
                ANY,
                ANY,
                golem_sci.chains.MAINNET,
            )

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.NodeProcess',
           Mock())
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.new_sci')
    def test_get_withdraw_gas_cost(self, new_sci):
        sci = Mock()
        sci.GAS_PRICE = 0
        sci.GAS_PER_PAYMENT = 0
        sci.GAS_BATCH_PAYMENT_BASE = 0
        sci.get_gate_address.return_value = None
        sci.GAS_GNT_TRANSFER = 222
        sci.GAS_WITHDRAW = 555
        gas_price = 123
        sci.get_current_gas_price.return_value = gas_price
        new_sci.return_value = sci

        ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

        cost = ets.get_withdraw_gas_cost(100, 'ETH')
        assert cost == 21000 * gas_price

        cost = ets.get_withdraw_gas_cost(200, 'GNT')
        assert cost == sci.GAS_WITHDRAW * gas_price

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.NodeProcess',
           Mock())
    @patch('golem.transactions.ethereum.ethereumtransactionsystem.new_sci')
    def test_withdraw(self, new_sci):
        sci = Mock()
        sci.GAS_PRICE = 0
        sci.GAS_PER_PAYMENT = 0
        sci.GAS_BATCH_PAYMENT_BASE = 0
        sci.get_gate_address.return_value = None
        new_sci.return_value = sci
        eth_balance = 400
        gnt_balance = 100
        gntb_balance = 200
        sci.get_eth_balance.return_value = eth_balance
        sci.get_gnt_balance.return_value = gnt_balance
        sci.get_gntb_balance.return_value = gntb_balance
        eth_tx = '0xee'
        gntb_tx = '0xfad'
        sci.transfer_eth.return_value = eth_tx
        sci.convert_gntb_to_gnt.return_value = gntb_tx
        destination = '0x' + 40 * 'd'

        ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        ets._faucet = False
        ets._run()

        # Unknown currency
        with self.assertRaises(ValueError):
            ets.withdraw(1, destination, 'asd')

        # Invalid address
        with self.assertRaisesRegex(ValueError, 'is not valid ETH address'):
            ets.withdraw(1, 'asd', 'ETH')

        # Not enough GNT
        with self.assertRaises(NotEnoughFunds):
            ets.withdraw(gnt_balance + gntb_balance + 1, destination, 'GNT')

        # Not enough ETH
        with self.assertRaises(NotEnoughFunds):
            ets.withdraw(eth_balance + 1, destination, 'ETH')

        # Enough GNTB
        res = ets.withdraw(gntb_balance - 1, destination, 'GNT')
        assert res == [gntb_tx]
        sci.convert_gntb_to_gnt.assert_called_once_with(
            destination,
            gntb_balance - 1,
        )
        sci.reset_mock()

        # Not enough GNTB
        with self.assertRaisesRegex(Exception, 'background operations'):
            ets.withdraw(gnt_balance + gntb_balance - 1, destination, 'GNT')
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
        with self.assertRaises(NotEnoughFunds):
            ets.withdraw(eth_balance - 3, destination, 'ETH', 4)
        sci.reset_mock()

        # Enough GNTB with lock
        res = ets.withdraw(gntb_balance - 1, destination, 'GNT', 1)
        sci.convert_gntb_to_gnt.assert_called_once_with(
            destination,
            gntb_balance - 1,
        )
        sci.reset_mock()

        # Not enough GNT with lock
        with self.assertRaises(NotEnoughFunds):
            ets.withdraw(gnt_balance + gntb_balance - 1, destination, 'GNT', 2)
        sci.reset_mock()

    @patch('golem.transactions.ethereum.ethereumtransactionsystem'
           '.EthereumTransactionSystem.concent_balance')
    def test_concent_deposit_enough(self, balance_mock):
        balance_mock.return_value = 10
        ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        cb = Mock()
        ets.concent_deposit(
            required=10,
            expected=40,
            reserved=1,
            cb=cb,
        )
        cb.assert_called_once_with()

    @patch('golem.transactions.ethereum.ethereumtransactionsystem'
           '.EthereumTransactionSystem.concent_balance')
    def test_concent_deposit_not_enough(self, balance_mock):
        balance_mock.return_value = 0
        ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        ets._gntb_balance = 0
        cb = Mock()
        with self.assertRaises(NotEnoughFunds):
            ets.concent_deposit(
                required=10,
                expected=40,
                reserved=1,
                cb=cb,
            )
        cb.assert_not_called()

    @patch('golem_sci.implementation.SCIImplementation.deposit_payment')
    @patch('golem.transactions.ethereum.ethereumtransactionsystem'
           '.EthereumTransactionSystem.concent_balance')
    def test_concent_deposit_done(self, balance_mock, deposit_mock):
        balance_mock.return_value = 0
        given_hash = object()
        deposit_mock.return_value = given_hash
        ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        ets._gntb_balance = 20
        ets.concent_deposit(
            required=10,
            expected=40,
            reserved=1,
        )
        deposit_mock.assert_called_once_with(20-1)


class FaucetTest(unittest.TestCase):

    @patch('requests.get')
    def test_error_code(self, get):
        addr = encode_hex(urandom(20))
        response = Mock(spec=requests.Response)
        response.status_code = 500
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @patch('requests.get')
    def test_error_msg(self, get):
        addr = encode_hex(urandom(20))
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 0, 'message': "Ooops!"}
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @patch('requests.get')
    def test_success(self, get):
        addr = encode_hex(urandom(20))
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 1486605259,
                                      'amount': 999999999999999}
        get.return_value = response
        assert tETH_faucet_donate(addr) is True
        assert get.call_count == 1
        assert addr in get.call_args[0][0]
