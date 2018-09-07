from os import urandom
from pathlib import Path
from typing import Optional
from unittest.mock import patch, Mock, ANY, PropertyMock
from unittest import TestCase

from eth_utils import encode_hex
from ethereum.utils import denoms
import requests

from golem.tools.testwithdatabase import TestWithDatabase
from golem.ethereum.transactionsystem import (
    TransactionSystem,
    tETH_faucet_donate,
)
from golem.ethereum.exceptions import NotEnoughFunds

PASSWORD = 'derp'


class TestTransactionSystem(TestWithDatabase):
    def setUp(self):
        super().setUp()
        self.sci = Mock()
        self.sci.GAS_PRICE = 10 ** 9
        self.sci.GAS_BATCH_PAYMENT_BASE = 30000
        self.sci.get_gate_address.return_value = None
        self.sci.get_block_number.return_value = 1223
        self.sci.get_current_gas_price.return_value = 10 ** 9
        self.sci.get_eth_balance.return_value = 0
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 0
        self.sci.GAS_PER_PAYMENT = 20000
        self.sci.REQUIRED_CONFS = 6
        self.ets = self._make_ets()

    def _make_ets(
            self,
            datadir: Optional[Path] = None,
            withdrawals: bool = True,
            password: str = PASSWORD,
            just_create: bool = False):
        with patch('golem.ethereum.transactionsystem.NodeProcess'),\
            patch('golem.ethereum.transactionsystem.new_sci',
                  return_value=self.sci):
            ets = TransactionSystem(
                datadir or self.new_path,
                Mock(
                    NODE_LIST=[],
                    FALLBACK_NODE_LIST=[],
                    CHAIN='test_chain',
                    FAUCET_ENABLED=False,
                    WITHDRAWALS_ENABLED=withdrawals,
                )
            )
            if not just_create:
                ets.set_password(password)
                ets._init()
            return ets

    @patch('golem.core.service.LoopingCallService.running',
           new_callable=PropertyMock)
    def test_stop(self, mock_is_service_running):
        with patch('twisted.internet.task.LoopingCall.start'), \
                patch('twisted.internet.task.LoopingCall.stop'):
            mock_is_service_running.return_value = False
            e = self._make_ets()

            mock_is_service_running.return_value = True
            e._payment_processor = Mock()  # noqa pylint: disable=no-member
            e.stop()
            e._payment_processor.sendout.assert_called_once_with(0)  # noqa pylint: disable=no-member

    @patch('golem.ethereum.transactionsystem.NodeProcess', Mock())
    @patch('golem.ethereum.transactionsystem.new_sci')
    def test_chain_arg(self, new_sci):
        new_sci.return_value = self.sci
        ets = TransactionSystem(
            self.new_path,
            Mock(
                NODE_LIST=[],
                FALLBACK_NODE_LIST=[],
                CHAIN='test_chain',
            )
        )
        ets.set_password(PASSWORD)
        ets._init()
        new_sci.assert_called_once_with(
            ANY,
            ANY,
            'test_chain',
            ANY,
            ANY,
        )

    def test_payment(self):
        subtask_id = 'derp'
        value = 10
        payee = '0x' + 40 * '1'
        self.ets.add_payment_info(subtask_id, value, payee)
        payments = self.ets.get_payments_list()
        assert len(payments) == 1
        assert payments[0]['subtask'] == subtask_id
        assert payments[0]['value'] == str(value)
        assert payments[0]['payee'] == payee

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
        eth_balance = 40 * denoms.ether
        gnt_balance = 10 * denoms.ether
        gntb_balance = 20 * denoms.ether
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
        assert res == gntb_tx
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
        assert res == eth_tx
        self.sci.transfer_eth.assert_called_once_with(dest, eth_balance - 1)
        self.sci.reset_mock()

        # Enough ETH with lock
        self.ets.lock_funds_for_payments(1, 1)
        locked_eth = self.ets.get_locked_eth()
        locked_gnt = self.ets.get_locked_gnt()
        assert 0 < locked_eth < eth_balance
        assert 0 < locked_gnt < gnt_balance
        res = self.ets.withdraw(eth_balance - locked_eth, dest, 'ETH')
        assert res == eth_tx
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

    def test_withdraw_disabled(self):
        ets = self._make_ets(withdrawals=False)
        with self.assertRaisesRegex(Exception, 'Withdrawals are disabled'):
            ets.withdraw(1, '0x' + 40 * '0', 'GNT')

    def test_locking_funds(self):
        eth_balance = 10 * denoms.ether
        gnt_balance = 1000 * denoms.ether
        self.sci.get_eth_balance.return_value = eth_balance
        self.sci.get_gntb_balance.return_value = gnt_balance
        self.ets._refresh_balances()

        assert self.ets.get_locked_eth() == 0
        assert self.ets.get_locked_gnt() == 0

        price = 5 * denoms.ether
        num = 3

        eth_estimation = self.ets.eth_for_batch_payment(num)
        self.ets.lock_funds_for_payments(price, num)
        locked_eth = self.ets.get_locked_eth()
        assert locked_eth == eth_estimation
        assert self.ets.get_locked_gnt() == price * num

        self.ets.unlock_funds_for_payments(price, num - 1)
        assert self.ets.get_locked_eth() == locked_eth // num
        assert self.ets.get_locked_gnt() == price

        self.ets.unlock_funds_for_payments(price, 1)
        assert self.ets.get_locked_eth() == 0
        assert self.ets.get_locked_gnt() == 0

        with self.assertRaisesRegex(NotEnoughFunds, 'GNT'):
            self.ets.lock_funds_for_payments(gnt_balance, 2)

        with self.assertRaisesRegex(Exception, "Can't unlock .* GNT"):
            self.ets.unlock_funds_for_payments(1, 1)

    def test_locking_funds_changing_gas_price(self):
        eth_balance = 10 * denoms.ether
        gnt_balance = 1000 * denoms.ether
        self.sci.get_eth_balance.return_value = eth_balance
        self.sci.get_gntb_balance.return_value = gnt_balance
        self.ets._refresh_balances()

        assert self.ets.get_locked_eth() == 0
        assert self.ets.get_locked_gnt() == 0

        self.ets.lock_funds_for_payments(5, 3)
        locked_eth = self.ets.get_locked_eth()
        self.sci.get_current_gas_price.return_value = 111
        assert self.ets.get_locked_eth() == locked_eth

    def test_convert_gnt(self):
        amount = 1000 * denoms.ether
        gate_addr = '0x' + 40 * '2'
        self.sci.get_gate_address.return_value = None
        self.sci.get_gnt_balance.return_value = amount
        self.sci.get_eth_balance.return_value = denoms.ether
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
        amount = 1000 * denoms.ether
        gate_addr = '0x' + 40 * '2'
        self.sci.get_current_gas_price.return_value = 0
        self.sci.GAS_TRANSFER_FROM_GATE = 5
        self.sci.get_gate_address.return_value = gate_addr
        self.sci.get_gnt_balance.side_effect = \
            lambda addr: amount if addr == gate_addr else 0
        self.sci.get_eth_balance.return_value = denoms.ether
        ets = self._make_ets()
        ets._refresh_balances()
        ets._try_convert_gnt()
        self.sci.transfer_from_gate.assert_called_once_with()
        self.sci.transfer_from_gate.reset_mock()
        ets._try_convert_gnt()
        self.sci.transfer_from_gate.assert_not_called()

    def test_subscriptions(self):
        self.sci.subscribe_to_batch_transfers.assert_called_once_with(
            None,
            self.sci.get_eth_address(),
            0,
            ANY,
        )

        block_number = 123
        self.sci.get_block_number.return_value = block_number
        with patch('golem.ethereum.transactionsystem.LoopingCallService.stop'):
            self.ets.stop()

        self.sci.reset_mock()
        self._make_ets()
        self.sci.subscribe_to_batch_transfers.assert_called_once_with(
            None,
            self.sci.get_eth_address(),
            block_number - self.sci.REQUIRED_CONFS - 1,
            ANY,
        )

    def test_concent_deposit_enough(self):
        self.sci.get_deposit_value.return_value = 10
        deferred = self.ets.concent_deposit(
            required=10,
            expected=40,
        )
        deferred.addErrback(lambda _: self.fail('shoud not fail'))
        assert deferred.called
        self.sci.deposit_payment.assert_not_called()

    def test_concent_deposit_not_enough(self):
        self.sci.get_deposit_value.return_value = 0
        self.ets._gntb_balance = 0
        with self.assertRaises(NotEnoughFunds):
            self.ets.concent_deposit(
                required=10,
                expected=40,
            )

    def test_concent_deposit_done(self):
        self.sci.get_deposit_value.return_value = 0
        self.ets._gntb_balance = 20
        self.ets._eth_balance = denoms.ether
        self.ets.lock_funds_for_payments(1, 1)
        self.ets.concent_deposit(
            required=10,
            expected=40,
        )
        self.sci.deposit_payment.assert_called_once_with(20 - 1)

    def test_check_payments(self):
        with patch.object(
            self.ets._incomes_keeper, 'update_overdue_incomes'
        ) as incomes:
            self.ets._run()
            incomes.assert_called_once()

    def test_no_password(self):
        ets = self._make_ets(just_create=True)
        with self.assertRaisesRegex(Exception, 'Invalid private key'):
            ets.start()

    def test_invalid_password(self):
        ets = self._make_ets(just_create=True)
        with self.assertRaisesRegex(Exception, 'MAC mismatch'):
            ets.set_password(PASSWORD + 'nope')

    def test_backwards_compatibility_privkey(self):
        ets = self._make_ets(datadir=self.new_path / 'other', just_create=True)
        privkey = b'\x21' * 32
        other_privkey = b'\x13' * 32
        address = '0x2BD0C9FE079c8FcA0E3352eb3D02839c371E5c41'
        password = 'Password1'
        ets.backwards_compatibility_privkey(privkey, password)
        with self.assertRaisesRegex(Exception, 'backward compatible'):
            ets.backwards_compatibility_privkey(other_privkey, password)
        ets.set_password(password)
        with patch('golem.ethereum.transactionsystem.new_sci',
                   return_value=self.sci) as new_sci:
            ets._init()
            new_sci.assert_called_once_with(ANY, address, ANY, ANY, ANY)

        # Shouldn't throw
        self._make_ets(datadir=self.new_path / 'other', password=password)


class FaucetTest(TestCase):

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
