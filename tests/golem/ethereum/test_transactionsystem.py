# pylint: disable=protected-access
from pathlib import Path
import sys
import time
from typing import Optional
from unittest.mock import patch, Mock, ANY, PropertyMock

from ethereum.utils import denoms
import faker
from freezegun import freeze_time
import golem_sci.contracts
import golem_sci.structs

from golem import model
from golem import testutils
from golem.ethereum import exceptions
from golem.ethereum.transactionsystem import TransactionSystem
from golem.ethereum.exceptions import NotEnoughFunds

fake = faker.Faker()
PASSWORD = 'derp'


class TransactionSystemBase(testutils.DatabaseFixture):
    def setUp(self):
        super().setUp()
        self.sci = Mock()
        self.sci.GAS_PRICE = 10 ** 9
        self.sci.GAS_BATCH_PAYMENT_BASE = 30000
        self.sci.get_gate_address.return_value = None
        self.sci.get_block_number.return_value = 1223
        self.sci.get_current_gas_price.return_value = self.sci.GAS_PRICE - 1
        self.sci.get_eth_balance.return_value = 0
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 0
        self.sci.GAS_PER_PAYMENT = 20000
        self.sci.REQUIRED_CONFS = 6
        self.sci.get_deposit_locked_until.return_value = 0
        self.ets = self._make_ets()

    def _make_ets(
            self,
            datadir: Optional[Path] = None,
            withdrawals: bool = True,
            password: str = PASSWORD,
            just_create: bool = False,
            provide_gntdeposit: bool = False):
        with patch('golem.ethereum.transactionsystem.NodeProcess'),\
            patch('golem.ethereum.transactionsystem.new_sci',
                  return_value=self.sci):
            contract_addresses = {}
            if provide_gntdeposit:
                contract_addresses[golem_sci.contracts.GNTDeposit] = 'test addr'
            ets = TransactionSystem(
                datadir=datadir or self.new_path,
                config=Mock(
                    NODE_LIST=[],
                    FALLBACK_NODE_LIST=[],
                    CHAIN='test_chain',
                    FAUCET_ENABLED=False,
                    WITHDRAWALS_ENABLED=withdrawals,
                    CONTRACT_ADDRESSES=contract_addresses,
                )
            )
            if not just_create:
                ets.set_password(password)
                ets._init()
            return ets


class TestTransactionSystem(TransactionSystemBase):
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
            datadir=self.new_path,
            config=Mock(
                NODE_LIST=[],
                FALLBACK_NODE_LIST=[],
                CHAIN='test_chain',
                CONTRACT_ADDRESSES={
                    golem_sci.contracts.GNTDeposit: 'some address',
                },
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
        eth_gas_cost = 21000
        self.sci.GAS_WITHDRAW = 555
        self.sci.estimate_transfer_eth_gas.return_value = eth_gas_cost

        cost = self.ets.get_withdraw_gas_cost(100, dest, 'ETH')
        assert cost == eth_gas_cost

        cost = self.ets.get_withdraw_gas_cost(200, dest, 'GNT')
        assert cost == self.sci.GAS_WITHDRAW

    def test_get_gas_price(self):
        test_gas_price = 1234
        self.sci.get_current_gas_price.return_value = test_gas_price
        ets = self._make_ets()

        self.assertEqual(ets.gas_price, test_gas_price)

    def test_get_gas_price_limit(self):
        ets = self._make_ets()

        self.assertEqual(ets.gas_price_limit, self.sci.GAS_PRICE)

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
        self.sci.get_gnt_balance.return_value = 0
        self.ets._refresh_balances()
        self.ets._try_convert_gnt()
        self.sci.transfer_gnt.assert_not_called()
        self.sci.transfer_from_gate.assert_not_called()

    def test_topup_while_convert(self):
        amount1 = 1000 * denoms.ether
        amount2 = 2000 * denoms.ether
        gate_addr = '0x' + 40 * '2'
        self.sci.get_gate_address.return_value = gate_addr
        self.sci.get_gnt_balance.return_value = amount1
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_current_gas_price.return_value = 0
        self.sci.GAS_GNT_TRANSFER = 2
        self.sci.GAS_TRANSFER_FROM_GATE = 5
        self.ets._refresh_balances()

        self.ets._try_convert_gnt()
        self.sci.open_gate.assert_not_called()
        self.sci.transfer_gnt.assert_called_once_with(gate_addr, amount1)
        self.sci.transfer_from_gate.assert_called_once_with()
        self.sci.transfer_gnt.reset_mock()
        self.sci.transfer_from_gate.reset_mock()

        # Top up with more GNT
        self.sci.get_gnt_balance.return_value = amount2
        self.ets._refresh_balances()
        self.ets._try_convert_gnt()
        self.sci.transfer_gnt.assert_called_once_with(gate_addr, amount2)
        self.sci.transfer_from_gate.assert_called_once_with()

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

    def test_check_payments(self, *_args):
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
            new_sci.assert_called_once_with(ANY, address, ANY, ANY, ANY, ANY)

        # Shouldn't throw
        self._make_ets(datadir=self.new_path / 'other', password=password)


class WithdrawTest(TransactionSystemBase):
    def setUp(self):
        super().setUp()
        self.eth_balance = 10 * denoms.ether
        self.gnt_balance = 1000 * denoms.ether
        self.gas_price = 10 ** 9
        self.gas_cost = 21000
        self.sci.get_eth_balance.return_value = self.eth_balance
        self.sci.get_gntb_balance.return_value = self.gnt_balance
        self.sci.get_current_gas_price.return_value = self.gas_price
        self.sci.estimate_transfer_eth_gas.return_value = self.gas_cost
        self.dest = '0x' + 40 * 'd'

        self.eth_tx = '0xee'
        self.gntb_tx = '0xfad'
        self.sci.transfer_eth.return_value = self.eth_tx
        self.sci.convert_gntb_to_gnt.return_value = self.gntb_tx

        self.ets._refresh_balances()

    def test_unknown_currency(self):
        with self.assertRaises(ValueError, msg="Unknown currency asd"):
            self.ets.withdraw(1, self.dest, 'asd')

    def test_invalid_address(self):
        with self.assertRaisesRegex(ValueError, 'is not valid ETH address'):
            self.ets.withdraw(1, 'asd', 'ETH')

    def test_not_enough_gnt(self):
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(self.gnt_balance + 1, self.dest, 'GNT')

    def test_not_enough_eth(self):
        with self.assertRaises(NotEnoughFunds):
            self.ets.withdraw(self.eth_balance + 1, self.dest, 'ETH')

    def test_enough_gnt(self):
        amount = 3 * denoms.ether
        res = self.ets.withdraw(amount, self.dest, 'GNT')
        assert res == self.gntb_tx
        self.sci.convert_gntb_to_gnt.assert_called_once_with(
            self.dest,
            amount,
            None,
        )

    def test_custom_gas_price_gnt(self):
        gas_price = 111
        amount = 3 * denoms.ether
        self.ets.withdraw(amount, self.dest, 'GNT', gas_price)
        self.sci.convert_gntb_to_gnt.assert_called_once_with(
            self.dest,
            amount,
            gas_price,
        )

    def test_enough_eth(self):
        amount = denoms.ether
        res = self.ets.withdraw(amount, self.dest, 'ETH')
        assert res == self.eth_tx
        self.sci.transfer_eth.assert_called_once_with(
            self.dest,
            amount - self.gas_price * self.gas_cost,
            self.gas_price,
        )

    def test_custom_gas_price_eth(self):
        gas_price = 1111
        amount = denoms.ether
        self.ets.withdraw(amount, self.dest, 'ETH', gas_price)
        self.sci.transfer_eth.assert_called_once_with(
            self.dest,
            amount - gas_price * self.gas_cost,
            gas_price,
        )

    def test_eth_with_lock(self):
        self.ets.lock_funds_for_payments(1, 1)
        locked_eth = self.ets.get_locked_eth()
        assert 0 < locked_eth < self.eth_balance
        self.ets.withdraw(self.eth_balance - locked_eth, self.dest, 'ETH')
        self.sci.transfer_eth.assert_called_once_with(
            self.dest,
            self.eth_balance - locked_eth - self.gas_price * self.gas_cost,
            self.gas_price,
        )

    def test_not_enough_eth_with_lock(self):
        self.ets.lock_funds_for_payments(1, 1)
        locked_eth = self.ets.get_locked_eth()
        assert 0 < locked_eth < self.eth_balance
        with self.assertRaisesRegex(NotEnoughFunds, 'ETH'):
            self.ets.withdraw(
                self.eth_balance - locked_eth + 1,
                self.dest,
                'ETH',
            )

    def test_gnt_with_lock(self):
        self.ets.lock_funds_for_payments(1, 1)
        locked_gnt = self.ets.get_locked_gnt()
        assert 0 < locked_gnt < self.gnt_balance
        self.ets.withdraw(self.gnt_balance - locked_gnt, self.dest, 'GNT')
        self.sci.convert_gntb_to_gnt.assert_called_once_with(
            self.dest,
            self.gnt_balance - locked_gnt,
            None,
        )

    def test_not_enough_gnt_with_lock(self):
        self.ets.lock_funds_for_payments(1, 1)
        locked_gnt = self.ets.get_locked_gnt()
        assert 0 < locked_gnt < self.gnt_balance
        with self.assertRaisesRegex(NotEnoughFunds, 'GNT'):
            self.ets.withdraw(
                self.gnt_balance + locked_gnt + 1,
                self.dest,
                'GNT',
            )

    def test_disabled(self):
        ets = self._make_ets(withdrawals=False)
        with self.assertRaisesRegex(Exception, 'Withdrawals are disabled'):
            ets.withdraw(1, self.dest, 'GNT')

    def test_lock_gntb(self):
        assert self.ets.get_available_gnt() == self.gnt_balance

        self.ets.withdraw(self.gnt_balance, self.dest, 'GNT')
        assert self.ets.get_available_gnt() == 0
        self.sci.on_transaction_confirmed.assert_called_once()

        self.sci.get_gntb_balance.return_value = 0
        self.ets._refresh_balances()
        self.sci.on_transaction_confirmed.call_args[0][1](Mock(status=True))
        assert self.ets.get_available_gnt() == 0


class ConcentDepositTest(TransactionSystemBase):
    def setUp(self):
        super().setUp()
        self.ets = self._make_ets(provide_gntdeposit=True)

    def _call_concent_deposit(self, *args, **kwargs):
        errback = Mock()
        callback = Mock()
        # pylint: disable=no-member
        self.ets.concent_deposit(*args, **kwargs) \
            .addCallback(callback).addErrback(errback)
        # pylint: enable=no-member
        if errback.called:
            failure = errback.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object
            failure.printDetailedTraceback(sys.stderr)
            failure.raiseException()

        callback.assert_called_once()
        return callback.call_args[0][0]  # noqa pylint: disable=unsubscriptable-object

    def test_enough_locked(self):
        self.sci.get_deposit_value.return_value = 10
        self.sci.get_deposit_locked_until.return_value = 0
        tx_hash = self._call_concent_deposit(
            required=10,
            expected=40,
        )
        self.assertIsNone(tx_hash)
        self.sci.deposit_payment.assert_not_called()
        self.sci.lock_deposit.assert_not_called()

    def test_enough_not_locked(self):
        self.sci.get_deposit_value.return_value = 10
        self.sci.get_deposit_locked_until.return_value = 1
        tx_hash = self._call_concent_deposit(
            required=10,
            expected=40,
        )
        self.assertIsNone(tx_hash)
        self.sci.deposit_payment.assert_not_called()
        self.sci.lock_deposit.assert_called()

    def test_not_enough(self):
        self.sci.GAS_TRANSFER_AND_CALL = 9999
        self.sci.get_deposit_value.return_value = 0
        self.ets._gntb_balance = 0
        with self.assertRaises(exceptions.NotEnoughFunds):
            self.ets.validate_concent_deposit_possibility(
                required=10,
                tasks_num=1,
            )

    def _prepare_concent_deposit(
            self,
            gntb_balance,
            subtask_price,
            subtask_count,
            callback,
    ):
        self.sci.get_deposit_value.return_value = 0
        self.sci.get_transaction_gas_price.return_value = 2
        self.ets._gntb_balance = gntb_balance
        self.ets._eth_balance = denoms.ether
        self.ets.lock_funds_for_payments(subtask_price, subtask_count)
        tx_hash = \
            '0x5e9880b3e9349b609917014690c7a0afcdec6dbbfbef3812b27b60d246ca10ae'
        self.sci.deposit_payment.return_value = tx_hash
        self.sci.on_transaction_confirmed.side_effect = callback
        return tx_hash

    @classmethod
    def _confirm_it(cls, tx_hash, cb):
        receipt = golem_sci.structs.TransactionReceipt(
            raw_receipt={
                'transactionHash': bytes.fromhex(tx_hash[2:]),
                'status': 1,
                'blockHash': bytes.fromhex(
                    'cbca49fb2c75ba2fada56c6ea7df5979444127d29b6b4e93a77'
                    '97dc22e97399c',
                ),
                'blockNumber': 2940769,
                'gasUsed': 21000,
            },
        )
        cb(receipt)

    def test_transaction_failed(self):
        gntb_balance = 20
        subtask_price = 1
        subtask_count = 1

        def fail_it(tx_hash, cb):
            receipt = golem_sci.structs.TransactionReceipt(
                raw_receipt={
                    'transactionHash': bytes.fromhex(tx_hash[2:]),
                    'status': 'not a status',
                    'blockHash': bytes.fromhex(
                        'cbca49fb2c75ba2fada56c6ea7df5979444127d29b6b4e93a77'
                        '97dc22e97399c',
                    ),
                    'blockNumber': 2940769,
                    'gasUsed': 21000,
                },
            )
            cb(receipt)

        self._prepare_concent_deposit(
            gntb_balance,
            subtask_price,
            subtask_count,
            fail_it,
        )

        with self.assertRaises(exceptions.DepositError):
            self._call_concent_deposit(
                required=10,
                expected=40,
            )
        deposit_value = gntb_balance - (subtask_price * subtask_count)
        self.sci.deposit_payment.assert_called_once_with(deposit_value)
        self.assertFalse(model.DepositPayment.select().exists())

    def test_done(self):
        gntb_balance = 20
        subtask_price = 1
        subtask_count = 1

        tx_hash = self._prepare_concent_deposit(
            gntb_balance,
            subtask_price,
            subtask_count,
            self._confirm_it,
        )

        db_tx_hash = self._call_concent_deposit(
            required=10,
            expected=40,
        )

        self.assertEqual(tx_hash, db_tx_hash)
        deposit_value = gntb_balance - (subtask_price * subtask_count)
        self.sci.deposit_payment.assert_called_once_with(deposit_value)
        dpayment = model.DepositPayment.get()
        for field, value in (
                ('status', model.PaymentStatus.confirmed),
                ('value', deposit_value),
                ('fee', 42000),
                ('tx', tx_hash),):
            self.assertEqual(getattr(dpayment, field), value)

    def test_gas_price_skyrocketing(self):
        self.sci.get_deposit_value.return_value = 0
        self.sci.get_gntb_balance.return_value = 20
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_current_gas_price.return_value = self.sci.GAS_PRICE
        self.ets._refresh_balances()
        with self.assertRaises(exceptions.LongTransactionTime):
            self.ets.validate_concent_deposit_possibility(
                required=10,
                tasks_num=1,
            )

    def test_gas_price_skyrocketing_forced(self):
        self.sci.get_current_gas_price.return_value = self.sci.GAS_PRICE
        self.sci.GAS_TRANSFER_AND_CALL = 90000
        self._prepare_concent_deposit(
            gntb_balance=20,
            subtask_price=1,
            subtask_count=1,
            callback=self._confirm_it,
        )
        self.ets.validate_concent_deposit_possibility(
            required=10,
            tasks_num=1,
            force=True
        )
        self._call_concent_deposit(
            required=10,
            expected=40,
        )


class ConcentWithdrawTest(TransactionSystemBase):
    def setUp(self):
        super().setUp()
        self.ets = self._make_ets(provide_gntdeposit=True)

    def test_timelocked(self):
        self.sci.get_deposit_locked_until.reset_mock()
        self.sci.get_deposit_locked_until.return_value = 0
        self.ets.concent_withdraw()
        self.sci.get_deposit_locked_until.assert_called_once_with(
            account_address=self.sci.get_eth_address(),
        )
        self.sci.withdraw_deposit.assert_not_called()

    @freeze_time('2018-10-01 14:00:00')
    def test_not_yet_unlocked(self):
        now = time.time()
        self.sci.get_deposit_locked_until.return_value = int(now) + 1
        self.sci.get_deposit_locked_until.reset_mock()
        self.ets.concent_withdraw()
        self.sci.get_deposit_locked_until.assert_called_once_with(
            account_address=self.sci.get_eth_address(),
        )
        self.sci.withdraw_deposit.assert_not_called()

    @freeze_time('2018-10-01 14:00:00')
    def test_unlocked(self):
        now = time.time()
        self.sci.get_deposit_locked_until.reset_mock()
        self.sci.get_deposit_locked_until.return_value = int(now)
        self.ets.concent_withdraw()
        self.sci.withdraw_deposit.assert_called_once_with()


class ConcentUnlockTest(TransactionSystemBase):
    def setUp(self):
        super().setUp()
        self.ets = self._make_ets(provide_gntdeposit=True)

    def test_empty(self):
        self.sci.get_deposit_value.return_value = 0
        self.ets.concent_unlock()
        self.sci.unlock_deposit.assert_not_called()

    def test_repeated_call(self):
        self.sci.get_deposit_value.return_value = 1
        self.sci.get_deposit_locked_until.return_value = \
            int(time.time()) - 1
        self.ets.concent_withdraw()
        self.ets.concent_withdraw()
        self.sci.withdraw_deposit.assert_called_once_with()
        self.sci.on_transaction_confirmed.assert_called_once()

        self.sci.on_transaction_confirmed.call_args[0][1](Mock())
        self.ets.concent_withdraw()
        assert self.sci.withdraw_deposit.call_count == 2

    @freeze_time('2018-10-01 14:00:00')
    @patch('golem.ethereum.transactionsystem.call_later')
    def test_full(self, call_later):
        self.sci.get_deposit_value.return_value = abs(fake.pyint()) + 1
        self.ets.concent_unlock()
        self.sci.unlock_deposit.assert_called_once_with()
        self.sci.on_transaction_confirmed.assert_called_once()

        delay = 10
        self.sci.get_deposit_locked_until.return_value = \
            int(time.time()) + delay
        self.sci.on_transaction_confirmed.call_args[0][1](Mock())
        call_later.assert_called_once_with(delay, self.ets.concent_withdraw)
