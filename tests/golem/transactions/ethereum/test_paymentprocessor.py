import random
import time
import uuid
import unittest
import unittest.mock as mock
from os import urandom

import golem_sci
from golem_sci.interface import TransactionReceipt
from eth_utils import encode_hex
from ethereum.utils import denoms, privtoaddr
from freezegun import freeze_time
from hexbytes import HexBytes

from golem.core.common import timestamp_to_datetime
from golem.ethereum.paymentprocessor import (
    PaymentProcessor,
    PAYMENT_MAX_DELAY,
)
from golem.model import Payment, PaymentStatus, PaymentDetails
from golem.testutils import DatabaseFixture


def wait_for(condition, timeout, step=0.1):
    for _ in range(int(timeout / step)):
        if condition():
            return True
        time.sleep(step)
    return False


def check_deadline(deadline, expected):
    return expected <= deadline <= expected + 1


class PaymentStatusTest(unittest.TestCase):

    def test_status(self):
        s = PaymentStatus(1)
        assert s == PaymentStatus.awaiting


class PaymentProcessorInternalTest(DatabaseFixture):
    """ In this suite we test internal logic of PaymentProcessor. The final
        Ethereum transactions are not inspected.
    """

    def setUp(self):
        DatabaseFixture.setUp(self)
        self.addr = encode_hex(privtoaddr(urandom(32)))
        self.sci = mock.Mock()
        self.sci.GAS_PRICE = 20
        self.sci.GAS_PER_PAYMENT = 300
        self.sci.GAS_BATCH_PAYMENT_BASE = 30
        self.sci.get_eth_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 0
        self.sci.get_eth_address.return_value = self.addr
        self.sci.get_current_gas_price.return_value = self.sci.GAS_PRICE
        latest_block = mock.Mock()
        latest_block.gas_limit = 10 ** 10
        self.sci.get_latest_block.return_value = latest_block
        self.pp = PaymentProcessor(self.sci)
        self.pp._gnt_converter = mock.Mock()
        self.pp._gnt_converter.is_converting.return_value = False
        self.pp._gnt_converter.get_gate_balance.return_value = 0

    def test_load_from_db(self):
        self.assertEqual([], self.pp._awaiting)

        subtask_id = str(uuid.uuid4())
        value = random.randint(1, 2**5)
        payee = encode_hex(urandom(32))
        payment = Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value
        )
        self.pp.add(payment)

        del self.pp._awaiting[:]
        self.pp.load_from_db()
        expected = [payment]
        self.assertEqual(expected, self.pp._awaiting)

        # Sent payments
        self.assertEqual({}, self.pp._inprogress)
        tx_hash = encode_hex(urandom(32))
        sent_payment = Payment.create(
            subtask='sent' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details=PaymentDetails(tx=tx_hash[2:]),
            status=PaymentStatus.sent
        )
        sent_payment2 = Payment.create(
            subtask='sent2' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details=PaymentDetails(tx=tx_hash[2:]),
            status=PaymentStatus.sent
        )
        self.pp.load_from_db()
        expected = {
            tx_hash: [sent_payment, sent_payment2],
        }
        self.assertEqual(expected, self.pp._inprogress)

    def test_reserved_eth(self):
        assert self.pp.reserved_eth == \
            self.sci.GAS_BATCH_PAYMENT_BASE * self.sci.GAS_PRICE

    def test_add_invalid_payment_status(self):
        a1 = urandom(20)
        p1 = Payment.create(
            subtask="p1",
            payee=a1,
            value=1,
            status=PaymentStatus.confirmed)
        assert p1.status is PaymentStatus.confirmed

        with self.assertRaises(RuntimeError):
            self.pp.add(p1)

    def test_monitor_progress(self):
        inprogress = self.pp._inprogress

        # Give 1 ETH and 99 GNT
        balance_eth = 1 * denoms.ether
        balance_gntb = 99 * denoms.ether
        self.sci.get_eth_balance.return_value = balance_eth
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = balance_gntb
        self.pp.CLOSURE_TIME_DELAY = 0

        assert self.pp.reserved_gntb == 0
        assert self.pp.reserved_eth == self.pp.ETH_BATCH_PAYMENT_BASE

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=urandom(20), value=gnt_value)
        self.pp.add(p)
        assert self.pp.reserved_gntb == gnt_value
        eth_reserved = \
            self.pp.ETH_BATCH_PAYMENT_BASE + self.pp.get_gas_cost_per_payment()
        assert self.pp.reserved_eth == eth_reserved

        tx_hash = '0xdead'
        self.sci.batch_transfer.return_value = tx_hash
        assert self.pp.sendout(0)
        assert self.sci.batch_transfer.call_count == 1

        assert len(inprogress) == 1
        assert tx_hash in inprogress
        assert inprogress[tx_hash] == [p]

        # Check payment status in the Blockchain
        self.sci.get_transaction_receipt.return_value = None
        self.sci.get_gntb_balance.return_value = balance_gntb - gnt_value
        self.pp.monitor_progress()
        balance_eth_after_sendout = balance_eth - \
            self.pp.ETH_BATCH_PAYMENT_BASE - \
            1 * self.pp.get_gas_cost_per_payment()
        self.sci.get_eth_balance.return_value = balance_eth_after_sendout
        assert len(inprogress) == 1
        assert tx_hash in inprogress
        assert inprogress[tx_hash] == [p]
        assert self.pp.reserved_gntb == 0
        assert self.pp.reserved_eth == self.pp.ETH_BATCH_PAYMENT_BASE

        self.pp.monitor_progress()
        assert len(inprogress) == 1
        assert self.pp.reserved_gntb == 0
        assert self.pp.reserved_eth == self.pp.ETH_BATCH_PAYMENT_BASE

        tx_block_number = 1337
        self.sci.get_block_number.return_value = tx_block_number
        receipt = TransactionReceipt({
            'transactionHash': HexBytes(tx_hash),
            'blockNumber': tx_block_number,
            'blockHash': HexBytes('0x' + 64 * 'f'),
            'gasUsed': 55001,
            'status': 1,
        })
        self.sci.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 1)

        self.sci.get_block_number.return_value =\
            tx_block_number + self.pp.REQUIRED_CONFIRMATIONS
        self.sci.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.confirmed)
        self.assertEqual(p.details.block_number, tx_block_number)
        self.assertEqual(p.details.block_hash, 64 * 'f')
        self.assertEqual(p.details.fee, 55001 * self.sci.GAS_PRICE)
        self.assertEqual(self.pp.reserved_gntb, 0)

    def test_failed_transaction(self):
        inprogress = self.pp._inprogress

        balance_eth = 1 * denoms.ether
        balance_gntb = 99 * denoms.ether
        self.sci.get_eth_balance.return_value = balance_eth
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = balance_gntb

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=urandom(20), value=gnt_value)
        self.pp.add(p)

        self.pp.CLOSURE_TIME_DELAY = 0
        tx_hash = '0xdead'
        self.sci.batch_transfer.return_value = tx_hash
        assert self.pp.sendout(0)

        # Check payment status in the Blockchain
        self.sci.get_transaction_receipt.return_value = None

        tx_block_number = 1337
        receipt = TransactionReceipt({
            'transactionHash': HexBytes(tx_hash),
            'blockNumber': tx_block_number,
            'blockHash': HexBytes('0x' + 64 * 'f'),
            'gasUsed': 55001,
            'status': 0,
        })
        self.sci.get_block_number.return_value = \
            tx_block_number + self.pp.REQUIRED_CONFIRMATIONS
        self.sci.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.awaiting)

        self.pp.deadline = int(time.time())
        assert self.pp.sendout(0)
        self.assertEqual(len(inprogress), 1)

        receipt.status = True
        self.sci.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.confirmed)
        self.assertEqual(p.details.block_number, tx_block_number)
        self.assertEqual(p.details.block_hash, 64 * 'f')
        self.assertEqual(p.details.fee, 55001 * self.sci.GAS_PRICE)
        self.assertEqual(self.pp.reserved_gntb, 0)

    def test_payment_timestamp(self):
        self.sci.get_eth_balance.return_value = denoms.ether

        ts = 7000000
        p = Payment.create(subtask="p1", payee=urandom(20), value=1)
        with freeze_time(timestamp_to_datetime(ts)):
            self.pp.add(p)
        self.assertEqual(ts, p.processed_ts)

        new_ts = 900000
        with freeze_time(timestamp_to_datetime(new_ts)):
            self.pp.add(p)
        self.assertEqual(ts, p.processed_ts)


def make_awaiting_payment(value=None, ts=None):
    p = mock.Mock()
    p.status = PaymentStatus.awaiting
    p.payee = urandom(20)
    p.value = value if value else random.randint(1, 10)
    p.subtask = '123'
    p.processed_ts = ts
    return p, golem_sci.Payment(encode_hex(p.payee), p.value)


class InteractionWithSmartContractInterfaceTest(DatabaseFixture):

    def setUp(self):
        DatabaseFixture.setUp(self)
        self.sci = mock.Mock()
        self.sci.GAS_BATCH_PAYMENT_BASE = 10
        self.sci.GAS_PER_PAYMENT = 1
        self.sci.GAS_PRICE = 20
        self.sci.get_gate_address.return_value = None
        self.sci.get_current_gas_price.return_value = self.sci.GAS_PRICE
        latest_block = mock.Mock()
        latest_block.gas_limit = 10 ** 10
        self.sci.get_latest_block.return_value = latest_block

        self.tx_hash = '0xdead'
        self.sci.batch_transfer.return_value = self.tx_hash

        self.pp = PaymentProcessor(self.sci)
        self.pp._gnt_converter = mock.Mock()
        self.pp._gnt_converter.is_converting.return_value = False
        self.pp._gnt_converter.get_gate_balance.return_value = 0

    def _assert_batch_transfer_called_with(
            self,
            payments,
            closure_time: int) -> None:
        self.sci.batch_transfer.assert_called_with(mock.ANY, closure_time)
        called_payments = self.sci.batch_transfer.call_args[0][0]
        assert len(called_payments) == len(payments)
        for expected, actual in zip(payments, called_payments):
            assert expected.payee == actual.payee
            assert expected.amount == actual.amount

    def test_batch_transfer(self):
        deadline = PAYMENT_MAX_DELAY
        self.pp.CLOSURE_TIME_DELAY = 0
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 1000 * denoms.ether

        assert not self.pp.sendout()
        self.sci.batch_transfer.assert_not_called()

        ts1 = 1230000
        ts2 = ts1 + 2 * deadline
        p1, scip1 = make_awaiting_payment(ts=ts1)
        p2, scip2 = make_awaiting_payment(ts=ts2)
        self.pp.add(p1)
        self.pp.add(p2)

        with freeze_time(timestamp_to_datetime(ts1 + deadline - 1)):
            assert not self.pp.sendout()
            self.sci.batch_transfer.assert_not_called()
        with freeze_time(timestamp_to_datetime(ts1 + deadline + 1)):
            assert self.pp.sendout()
            self._assert_batch_transfer_called_with(
                [scip1],
                ts1,
            )
            self.sci.batch_transfer.reset_mock()

        with freeze_time(timestamp_to_datetime(ts2 + deadline - 1)):
            assert not self.pp.sendout()
            self.sci.batch_transfer.assert_not_called()
        with freeze_time(timestamp_to_datetime(ts2 + deadline + 1)):
            assert self.pp.sendout()
            self._assert_batch_transfer_called_with(
                [scip2],
                ts2,
            )
            self.sci.batch_transfer.reset_mock()

    def test_closure_time(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 1000 * denoms.ether

        p1, scip1 = make_awaiting_payment()
        p2, scip2 = make_awaiting_payment()
        p5, scip5 = make_awaiting_payment()
        with freeze_time(timestamp_to_datetime(1000000)):
            self.pp.add(p1)
        with freeze_time(timestamp_to_datetime(2000000)):
            self.pp.add(p2)
        with freeze_time(timestamp_to_datetime(5000000)):
            self.pp.add(p5)

        closure_time = 2000000
        time_value = closure_time + self.pp.CLOSURE_TIME_DELAY
        with freeze_time(timestamp_to_datetime(time_value)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip1, scip2],
                closure_time)
            self.sci.batch_transfer.reset_mock()

        closure_time = 4000000
        time_value = closure_time + self.pp.CLOSURE_TIME_DELAY
        with freeze_time(timestamp_to_datetime(time_value)):
            self.pp.sendout(0)
            self.sci.batch_transfer.assert_not_called()
            self.sci.batch_transfer.reset_mock()

        closure_time = 5000000
        time_value = closure_time + self.pp.CLOSURE_TIME_DELAY
        with freeze_time(timestamp_to_datetime(time_value)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip5],
                closure_time)
            self.sci.batch_transfer.reset_mock()

    def test_short_on_gnt(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 4 * denoms.ether
        self.pp.CLOSURE_TIME_DELAY = 0

        p1, scip1 = make_awaiting_payment(value=1 * denoms.ether, ts=1)
        p2, scip2 = make_awaiting_payment(value=2 * denoms.ether, ts=2)
        p5, scip5 = make_awaiting_payment(value=5 * denoms.ether, ts=3)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p5)

        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip1, scip2],
                2)
            self.sci.batch_transfer.reset_mock()

        self.sci.get_gntb_balance.return_value = 5 * denoms.ether
        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip5],
                3)
            self.sci.batch_transfer.reset_mock()

    def test_short_on_gnt_closure_time(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 4 * denoms.ether
        self.pp.CLOSURE_TIME_DELAY = 0
        ts1 = 1000
        ts2 = 2000

        p1, scip1 = make_awaiting_payment(value=1 * denoms.ether, ts=ts1)
        p2, scip2 = make_awaiting_payment(value=2 * denoms.ether, ts=ts2)
        p5, scip5 = make_awaiting_payment(value=5 * denoms.ether, ts=ts2)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p5)

        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip1],
                ts1)
            self.sci.batch_transfer.reset_mock()

        self.sci.get_gntb_balance.return_value = 10 * denoms.ether
        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip2, scip5],
                ts2)
            self.sci.batch_transfer.reset_mock()

    def test_short_on_eth(self):
        self.sci.get_eth_balance.return_value = self.sci.GAS_PRICE * \
            (self.sci.GAS_BATCH_PAYMENT_BASE + 2 * self.sci.GAS_PER_PAYMENT)
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 1000 * denoms.ether
        self.pp.CLOSURE_TIME_DELAY = 0

        p1, scip1 = make_awaiting_payment(value=1, ts=1)
        p2, scip2 = make_awaiting_payment(value=2, ts=2)
        p5, scip5 = make_awaiting_payment(value=5, ts=3)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p5)

        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip1, scip2],
                2)
            self.sci.batch_transfer.reset_mock()

        self.sci.get_eth_balance.return_value = denoms.ether
        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip5],
                3)
            self.sci.batch_transfer.reset_mock()

    def test_sorted_payments(self):
        self.sci.get_eth_balance.return_value = 1000 * denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 1000 * denoms.ether
        self.pp.CLOSURE_TIME_DELAY = 0

        p1, _ = make_awaiting_payment(value=1, ts=300000)
        p2, scip2 = make_awaiting_payment(value=2, ts=200000)
        p3, scip3 = make_awaiting_payment(value=3, ts=100000)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p3)

        with freeze_time(timestamp_to_datetime(200000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with([scip3, scip2], 200000)

    def test_batch_transfer_throws(self):
        self.sci.get_eth_balance.return_value = 1000 * denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 1000 * denoms.ether
        self.pp.CLOSURE_TIME_DELAY = 0

        ts = 100000
        p, scip = make_awaiting_payment(value=1, ts=ts)
        self.pp.add(p)
        self.sci.batch_transfer.side_effect = Exception

        with freeze_time(timestamp_to_datetime(ts)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with([scip], ts)
            self.sci.batch_transfer.reset_mock()

        self.sci.batch_transfer.side_effect = None
        with freeze_time(timestamp_to_datetime(ts)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with([scip], ts)

    def test_block_gas_limit(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntb_balance.return_value = 1000 * denoms.ether
        self.sci.get_latest_block.return_value.gas_limit = \
            (self.sci.GAS_BATCH_PAYMENT_BASE + self.sci.GAS_PER_PAYMENT) /\
            self.pp.BLOCK_GAS_LIMIT_RATIO
        self.pp.CLOSURE_TIME_DELAY = 0

        p1, scip1 = make_awaiting_payment(value=1, ts=1)
        p2, _ = make_awaiting_payment(value=2, ts=2)
        self.pp.add(p1)
        self.pp.add(p2)

        with freeze_time(timestamp_to_datetime(10000)):
            self.pp.sendout(0)
            self._assert_batch_transfer_called_with(
                [scip1],
                1)
            self.sci.batch_transfer.reset_mock()
