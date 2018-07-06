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

    def setUp(self):
        super().setUp()
        self.sci = Mock()
        self.sci.GAS_PRICE = 10 ** 9
        self.sci.GAS_BATCH_PAYMENT_BASE = 30000
        self.sci.get_gate_address.return_value = None
        self.sci.get_current_gas_price.return_value = 10 ** 9
        self.sci.GAS_PER_PAYMENT = 20000
        with patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                   'new_sci', return_value=self.sci),\
            patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                  'NodeProcess'):
            self.ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)

    def test_invalid_private_key(self):
        with self.assertRaises(ValueError):
            EthereumTransactionSystem(self.tempdir, "not a private key")

    @patch('golem.core.service.LoopingCallService.running',
           new_callable=PropertyMock)
    def test_stop(self, mock_is_service_running):
        with patch('twisted.internet.task.LoopingCall.start'), \
                patch('twisted.internet.task.LoopingCall.stop'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'new_sci'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'PaymentProcessor'), \
                patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                      'NodeProcess') as node_mock:
            node_mock.return_value = node_mock

            mock_is_service_running.return_value = False
            e = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
            node_mock.start.assert_called_once_with(None)
            e.start()

            mock_is_service_running.return_value = True
            e.stop()
            node_mock.stop.assert_called_once_with()
            e.payment_processor.sendout.assert_called_once_with(0)  # noqa pylint: disable=no-member

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.NodeProcess',
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

    def test_get_withdraw_gas_cost(self):
        dest = '0x' + 40 * '0'
        gas_price = 123
        eth_gas_cost = 21000
        self.sci.GAS_WITHDRAW = 555
        self.sci.get_current_gas_price.return_value = gas_price
        self.sci.estimate_transfer_eth_gas.return_value = eth_gas_cost

        cost = self.ets.get_withdraw_gas_cost(100, dest, 'ETH')
        assert cost == eth_gas_cost * gas_price

        cost = self.ets.get_withdraw_gas_cost(200, dest, 'GNT')
        assert cost == self.sci.GAS_WITHDRAW * gas_price

    def test_withdraw(self):
        eth_balance = 40 * 10 ** 18
        gnt_balance = 10 * 10 ** 18
        gntb_balance = 20 * 10 ** 18
        self.sci.get_eth_balance.return_value = eth_balance
        self.sci.get_gnt_balance.return_value = gnt_balance
        self.sci.get_gntb_balance.return_value = gntb_balance
        eth_tx = '0xee'
        gntb_tx = '0xfad'
        self.sci.transfer_eth.return_value = eth_tx
        self.sci.convert_gntb_to_gnt.return_value = gntb_tx
        dest = '0x' + 40 * 'd'

        self.ets._refresh_balances()

        # Unknown currency
        with self.assertRaises(ValueError):
            self.ets.withdraw(1, dest, 'asd')

        # Invalid address
        with self.assertRaisesRegex(ValueError, 'is not valid ETH address'):
            self.ets.withdraw(1, 'asd', 'ETH')

        # Not enough GNT
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(gnt_balance + gntb_balance + 1, dest, 'GNT')

        # Not enough ETH
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(eth_balance + 1, dest, 'ETH')

        # Enough GNTB
        res = self.ets.withdraw(gntb_balance - 1, dest, 'GNT')
        assert res == [gntb_tx]
        self.sci.convert_gntb_to_gnt.assert_called_once_with(
            dest,
            gntb_balance - 1,
        )
        self.sci.reset_mock()

        # Not enough GNTB
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(gnt_balance + gntb_balance - 1, dest, 'GNT')
        self.sci.reset_mock()

        # Enough ETH
        res = self.ets.withdraw(eth_balance - 1, dest, 'ETH')
        assert res == [eth_tx]
        self.sci.transfer_eth.assert_called_once_with(dest, eth_balance - 1)
        self.sci.reset_mock()

        # Enough ETH with lock
        self.ets.lock_funds_for_payments(1, 1)
        locked_eth = self.ets.get_locked_eth()
        locked_gnt = self.ets.get_locked_gnt()
        assert 0 < locked_eth < eth_balance
        assert 0 < locked_gnt < gnt_balance
        res = self.ets.withdraw(eth_balance - locked_eth, dest, 'ETH')
        assert res == [eth_tx]
        self.sci.transfer_eth.assert_called_once_with(
            dest,
            eth_balance - locked_eth,
        )
        self.sci.reset_mock()

        # Not enough ETH with lock
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(eth_balance - locked_eth + 1, dest, 'ETH')
        self.sci.reset_mock()

        # Enough GNTB with lock
        res = self.ets.withdraw(gntb_balance - locked_gnt, dest, 'GNT')
        self.sci.convert_gntb_to_gnt.assert_called_once_with(
            dest,
            gntb_balance - 1,
        )
        self.sci.reset_mock()

        # Not enough GNT with lock
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(gntb_balance + locked_gnt + 1, dest, 'GNT')
        self.sci.reset_mock()

    def test_locking_funds(self):
        eth_balance = 10 * 10 ** 18
        gnt_balance = 1000 * 10 ** 18
        self.sci.get_eth_balance.return_value = eth_balance
        self.sci.get_gntb_balance.return_value = gnt_balance
        self.ets._refresh_balances()

        assert self.ets.get_locked_eth() == 0
        assert self.ets.get_locked_gnt() == 0

        price = 5 * 10 ** 18
        num = 3

        self.ets.lock_funds_for_payments(price, num)
        assert self.ets.get_locked_eth() == \
            self.ets._eth_for_batch_payment(num) + \
            self.ets._eth_base_for_batch_payment()
        assert self.ets.get_locked_gnt() == price * num

        self.ets.unlock_funds_for_payments(price, num - 1)
        assert self.ets.get_locked_eth() == \
            self.ets._eth_for_batch_payment(1) + \
            self.ets._eth_base_for_batch_payment()
        assert self.ets.get_locked_gnt() == price

        self.ets.unlock_funds_for_payments(price, 1)
        assert self.ets.get_locked_eth() == 0
        assert self.ets.get_locked_gnt() == 0

        with self.assertRaisesRegex(NotEnoughFunds, 'GNT'):
            self.ets.lock_funds_for_payments(gnt_balance, 2)

        with self.assertRaisesRegex(Exception, "Can't unlock .* GNT"):
            self.ets.unlock_funds_for_payments(1, 1)

    def test_convert_gnt(self):
        amount = 1000 * 10 ** 18
        gate_addr = '0x' + 40 * '2'
        self.sci.get_gate_address.return_value = None
        self.sci.get_gnt_balance.return_value = amount
        self.sci.get_eth_balance.return_value = 10 ** 18
        self.sci.get_current_gas_price.return_value = 0
        self.sci.GAS_OPEN_GATE = 10
        self.sci.GAS_GNT_TRANSFER = 2
        self.sci.GAS_TRANSFER_FROM_GATE = 5
        self.ets._refresh_balances()

        self.ets._try_convert_gnt()
        self.sci.open_gate.assert_called_once_with()
        self.sci.open_gate.reset_mock()
        self.ets._try_convert_gnt()
        self.sci.open_gate.assert_not_called()

        self.sci.get_gate_address.return_value = gate_addr
        self.ets._try_convert_gnt()
        self.sci.open_gate.assert_not_called()
        self.sci.transfer_gnt.assert_called_once_with(gate_addr, amount)
        self.sci.transfer_from_gate.assert_called_once_with()
        self.sci.transfer_gnt.reset_mock()
        self.sci.transfer_from_gate.reset_mock()
        self.ets._try_convert_gnt()
        self.sci.transfer_gnt.assert_not_called()
        self.sci.transfer_from_gate.assert_not_called()

    def test_unfinished_gnt_conversion(self):
        amount = 1000 * 10 ** 18
        gate_addr = '0x' + 40 * '2'
        self.sci.get_current_gas_price.return_value = 0
        self.sci.GAS_TRANSFER_FROM_GATE = 5
        self.sci.get_gate_address.return_value = gate_addr
        self.sci.get_gnt_balance.side_effect = \
            lambda addr: amount if addr == gate_addr else 0
        self.sci.get_eth_balance.return_value = 10 ** 18
        with patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                   'new_sci', return_value=self.sci),\
            patch('golem.transactions.ethereum.ethereumtransactionsystem.'
                  'NodeProcess'):
            ets = EthereumTransactionSystem(self.tempdir, PRIV_KEY)
        ets._refresh_balances()
        ets._try_convert_gnt()
        self.sci.transfer_from_gate.assert_called_once_with()
        self.sci.transfer_from_gate.reset_mock()
        ets._try_convert_gnt()
        self.sci.transfer_from_gate.assert_not_called()

    def test_concent_deposit_enough(self):
        self.sci.get_deposit_value.return_value = 10
        cb = Mock()
        self.ets.concent_deposit(
            required=10,
            expected=40,
            cb=cb,
        )
        cb.assert_called_once_with()
        self.sci.deposit_payment.assert_not_called()

    def test_concent_deposit_not_enough(self):
        self.sci.get_deposit_value.return_value = 0
        self.ets._gntb_balance = 0
        cb = Mock()
        with self.assertRaises(NotEnoughFunds):
            self.ets.concent_deposit(
                required=10,
                expected=40,
                cb=cb,
            )
        cb.assert_not_called()

    def test_concent_deposit_done(self):
        self.sci.get_deposit_value.return_value = 0
        self.ets._gntb_balance = 20
        self.ets._eth_balance = 10 ** 18
        self.ets.lock_funds_for_payments(1, 1)
        self.ets.concent_deposit(
            required=10,
            expected=40,
        )
        self.sci.deposit_payment.assert_called_once_with(20 - 1)


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
