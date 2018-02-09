import random
import requests
import time
import unittest
from os import urandom

import mock
from ethereum.utils import denoms, privtoaddr
from freezegun import freeze_time
from mock import patch, Mock
from twisted.internet.task import Clock

from golem.core.common import timestamp_to_datetime
from golem.ethereum.paymentprocessor import PaymentProcessor, tETH_faucet_donate
from golem.model import Payment, PaymentStatus
from golem.testutils import DatabaseFixture
from golem.utils import encode_hex


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

    def test_status2(self):
        s = PaymentStatus.awaiting
        assert s == PaymentStatus.awaiting


class PaymentProcessorInternalTest(DatabaseFixture):
    """ In this suite we test internal logic of PaymentProcessor. The final
        Ethereum transactions are not inspected.
    """

    def setUp(self):
        DatabaseFixture.setUp(self)
        self.addr = '0x' + encode_hex(privtoaddr(urandom(32)))
        self.sci = mock.Mock()
        self.sci.GAS_PRICE = 20
        self.sci.GAS_PER_PAYMENT = 300
        self.sci.GAS_BATCH_PAYMENT_BASE = 30
        self.sci.get_eth_balance.return_value = 0
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 0
        self.sci.get_eth_address.return_value = self.addr
        # FIXME: PaymentProcessor should be started and stopped!
        self.pp = PaymentProcessor(self.sci)
        self.pp._loopingCall.clock = Clock()  # Disable looping call.
        self.pp._gnt_converter = mock.Mock()
        self.pp._gnt_converter.is_converting.return_value = False

    def test_eth_balance(self):
        expected_balance = random.randint(0, 2**128 - 1)
        self.sci.get_eth_balance.return_value = expected_balance
        b = self.pp.eth_balance()
        assert b == expected_balance
        b = self.pp.eth_balance()
        assert b == expected_balance
        self.sci.get_eth_balance.assert_called_once_with(self.addr)

    def test_gnt_balance(self):
        expected_balance = 13
        self.sci.get_gnt_balance.return_value = expected_balance
        self.sci.get_gntw_balance.return_value = 0
        b = self.pp.gnt_balance()
        assert b == expected_balance
        self.sci.get_gnt_balance.return_value = 16
        b = self.pp.gnt_balance()
        assert b == expected_balance
        self.sci.get_gnt_balance.assert_called_once()

    def test_eth_balance_refresh(self):
        expected_balance = random.randint(0, 2**128 - 1)
        self.sci.get_eth_balance.return_value = expected_balance
        b = self.pp.eth_balance()
        assert b == expected_balance
        self.sci.get_eth_balance.assert_called_once_with(self.addr)
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        assert self.sci.get_eth_balance.call_count == 2

    def test_available_eth(self):
        eth = random.randint(1, 10 * denoms.ether)
        self.sci.get_eth_balance.return_value = eth
        eth_available = eth - self.pp.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == eth_available

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

    @patch('golem.ethereum.paymentprocessor.tETH_faucet_donate')
    def test_faucet(self, donate):
        self.pp._PaymentProcessor__faucet = True
        self.pp.get_ether_from_faucet()
        donate.assert_called_once_with(self.addr)

    @freeze_time(timestamp_to_datetime(10))
    def test_payment_deadline(self):
        a1 = urandom(20)
        a2 = urandom(20)
        a3 = urandom(20)

        self.sci.get_eth_balance.return_value = 100 * denoms.ether

        now = int(time.time())
        self.pp.add(Payment.create(subtask="p1", payee=a1, value=1))
        assert check_deadline(self.pp.deadline, now + self.pp.DEFAULT_DEADLINE)

        self.pp.add(
            Payment.create(subtask="p2", payee=a2, value=1), deadline=20000)
        assert check_deadline(self.pp.deadline, now + self.pp.DEFAULT_DEADLINE)

        self.pp.add(Payment.create(subtask="p3", payee=a2, value=1), deadline=1)
        assert check_deadline(self.pp.deadline, now + 1)

        self.pp.add(Payment.create(subtask="p4", payee=a3, value=1))
        assert check_deadline(self.pp.deadline, now + 1)

        self.pp.add(Payment.create(subtask="p5", payee=a3, value=1), deadline=1)
        assert check_deadline(self.pp.deadline, now + 1)

        self.pp.add(Payment.create(subtask="p6", payee=a3, value=1), deadline=0)
        assert check_deadline(self.pp.deadline, now)

        self.pp.add(
            Payment.create(subtask="p7", payee=a3, value=1), deadline=-1)
        assert check_deadline(self.pp.deadline, now - 1)

    @freeze_time(timestamp_to_datetime(10))
    def test_payment_deadline_not_reached(self):
        a1 = urandom(20)

        self.sci.get_eth_balance.return_value = 100 * denoms.ether

        now = int(time.time())
        inf = now + 12 * 30 * 24 * 60 * 60
        deadline = self.pp.deadline
        assert self.pp.deadline > inf
        assert not self.pp.sendout()
        assert self.pp.deadline == deadline

        p = Payment.create(subtask="p1", payee=a1, value=1111)
        self.pp.add(p, deadline=1111)
        assert check_deadline(self.pp.deadline, now + 1111)
        assert not self.pp.sendout()
        assert check_deadline(self.pp.deadline, now + 1111)

    def test_monitor_progress(self):
        inprogress = self.pp._inprogress

        # Give 1 ETH and 99 GNT
        balance_eth = 1 * denoms.ether
        balance_gntw = 99 * denoms.ether
        self.sci.get_eth_balance.return_value = balance_eth
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = balance_gntw
        self.pp.CLOSURE_TIME_DELAY = 0

        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gntw
        assert self.pp._eth_reserved() == self.pp.ETH_BATCH_PAYMENT_BASE
        eth_available = balance_eth - self.pp.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == eth_available

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=urandom(20), value=gnt_value)
        self.pp.add(p)
        assert self.pp._gnt_reserved() == gnt_value
        assert self.pp._gnt_available() == balance_gntw - gnt_value
        eth_reserved = self.pp.ETH_BATCH_PAYMENT_BASE + self.pp.ETH_PER_PAYMENT
        assert self.pp._eth_reserved() == eth_reserved
        eth_available = balance_eth - eth_reserved
        assert self.pp._eth_available() == eth_available

        self.pp.deadline = int(time.time())
        tx_hash = '0xdead'
        self.sci.batch_transfer.return_value = tx_hash
        assert self.pp.sendout()
        assert self.sci.batch_transfer.call_count == 1

        assert len(inprogress) == 1
        assert tx_hash in inprogress
        assert inprogress[tx_hash] == [p]

        # Check payment status in the Blockchain
        self.sci.get_transaction_receipt.return_value = None
        self.sci.get_gntw_balance.return_value = balance_gntw - gnt_value
        self.pp.monitor_progress()
        balance_eth_after_sendout = balance_eth - \
            self.pp.ETH_BATCH_PAYMENT_BASE - \
            1 * self.pp.ETH_PER_PAYMENT
        self.sci.get_eth_balance.return_value = balance_eth_after_sendout
        assert len(inprogress) == 1
        assert tx_hash in inprogress
        assert inprogress[tx_hash] == [p]
        assert self.pp.gnt_balance(True) == balance_gntw - gnt_value
        assert self.pp.eth_balance(True) == balance_eth_after_sendout
        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gntw - gnt_value
        assert self.pp._eth_reserved() == \
            self.pp.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == \
            balance_eth_after_sendout - self.pp.ETH_BATCH_PAYMENT_BASE

        self.pp.monitor_progress()
        assert len(inprogress) == 1
        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gntw - gnt_value
        assert self.pp._eth_reserved() == \
            self.pp.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == \
            balance_eth_after_sendout - self.pp.ETH_BATCH_PAYMENT_BASE

        tx_block_number = 1337
        self.sci.get_block_number.return_value = tx_block_number
        receipt = {
            'blockNumber': tx_block_number,
            'blockHash': '0x' + 64 * 'f',
            'gasUsed': 55001,
            'status': '0x1',
        }
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
        self.assertEqual(self.pp._gnt_reserved(), 0)

    def test_failed_transaction(self):
        inprogress = self.pp._inprogress

        balance_eth = 1 * denoms.ether
        balance_gntw = 99 * denoms.ether
        self.sci.get_eth_balance.return_value = balance_eth
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = balance_gntw

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=urandom(20), value=gnt_value)
        self.pp.add(p)

        self.pp.deadline = int(time.time())
        self.pp.CLOSURE_TIME_DELAY = 0
        tx_hash = '0xdead'
        self.sci.batch_transfer.return_value = tx_hash
        assert self.pp.sendout()

        # Check payment status in the Blockchain
        self.sci.get_transaction_receipt.return_value = None

        tx_block_number = 1337
        receipt = {
            'blockNumber': tx_block_number,
            'blockHash': '0x' + 64 * 'f',
            'gasUsed': 55001,
            'status': '0x0',
        }
        self.sci.get_block_number.return_value = \
            tx_block_number + self.pp.REQUIRED_CONFIRMATIONS
        self.sci.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.awaiting)

        self.pp.deadline = int(time.time())
        assert self.pp.sendout()
        self.assertEqual(len(inprogress), 1)

        receipt['status'] = '0x1'
        self.sci.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.confirmed)
        self.assertEqual(p.details.block_number, tx_block_number)
        self.assertEqual(p.details.block_hash, 64 * 'f')
        self.assertEqual(p.details.fee, 55001 * self.sci.GAS_PRICE)
        self.assertEqual(self.pp._gnt_reserved(), 0)

    def test_payment_timestamp(self):
        self.sci.get_eth_balance.return_value = denoms.ether

        ts = 7
        p = Payment.create(subtask="p1", payee=urandom(20), value=1)
        with freeze_time(timestamp_to_datetime(ts)):
            self.pp.add(p)
        self.assertEqual(ts, p.processed_ts)

        new_ts = 9
        with freeze_time(timestamp_to_datetime(new_ts)):
            self.pp.add(p)
        self.assertEqual(ts, p.processed_ts)

    def test_get_ether_and_gnt_failure(self):
        self.pp.monitor_progress = Mock()
        self.sci.is_synchronized.return_value = True
        self.pp.sendout = Mock()

        self.pp.get_gnt_from_faucet = Mock(return_value=False)
        self.pp.get_ether_from_faucet = Mock(return_value=False)

        self.pp._run()
        assert not self.pp.monitor_progress.called
        assert not self.pp.sendout.called

    def test_get_gnt_failure(self):
        self.pp.monitor_progress = Mock()
        self.sci.is_synchronized.return_value = True
        self.pp.sendout = Mock()

        self.pp.get_gnt_from_faucet = Mock(return_value=False)
        self.pp.get_ether_from_faucet = Mock(return_value=True)

        self.pp._run()
        assert not self.pp.monitor_progress.called
        assert not self.pp.sendout.called

    def test_get_ether(self):
        self.pp.monitor_progress = Mock()
        self.sci.is_synchronized.return_value = True
        self.pp.sendout = Mock()

        self.pp.get_gnt_from_faucet = Mock(return_value=True)
        self.pp.get_ether_from_faucet = Mock(return_value=True)

        self.pp._run()
        assert self.pp.monitor_progress.called
        assert self.pp.sendout.called

    def test_get_ether_sci_failure(self):
        # given
        self.pp.monitor_progress = Mock()
        self.sci.is_synchronized.return_value = True
        self.pp.sendout = Mock()

        self.pp._PaymentProcessor__faucet = True

        self.sci.get_eth_balance.return_value = None
        self.sci.get_gnt_balance.return_value = None
        self.sci.get_gntw_balance.return_value = None

        # when
        self.pp._run()

        # then
        assert not self.pp.monitor_progress.called
        assert not self.pp.sendout.called


def make_awaiting_payment(value=None, ts=None):
    p = mock.Mock()
    p.status = PaymentStatus.awaiting
    p.payee = urandom(20)
    p.value = value if value else random.randint(1, 10)
    p.subtask = '123'
    p.processed_ts = ts
    return p


class InteractionWithSmartContractInterfaceTest(DatabaseFixture):

    def setUp(self):
        DatabaseFixture.setUp(self)
        self.sci = mock.Mock()
        self.sci.GAS_BATCH_PAYMENT_BASE = 10
        self.sci.GAS_PER_PAYMENT = 1
        self.sci.GAS_PRICE = 20

        self.tx_hash = '0xdead'
        self.sci.batch_transfer.return_value = self.tx_hash

        self.pp = PaymentProcessor(self.sci)
        self.pp._gnt_converter = mock.Mock()
        self.pp._gnt_converter.is_converting.return_value = False

    def test_faucet(self):
        self.pp._PaymentProcessor__faucet = True

        self.sci.get_gnt_balance.return_value = 1000 * denoms.ether
        self.sci.get_gntw_balance.return_value = 1000 * denoms.ether
        self.assertTrue(self.pp.get_gnt_from_faucet())
        self.sci.request_from_faucet.assert_not_called()

        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 0
        self.assertFalse(self.pp.get_gnt_from_faucet())
        self.sci.request_gnt_from_faucet.assert_called_once()

    @freeze_time(timestamp_to_datetime(0))
    def test_batch_transfer(self):
        self.pp.deadline = 0
        self.pp.CLOSURE_TIME_DELAY = 0
        self.assertFalse(self.pp.sendout())

        p1 = make_awaiting_payment()
        p2 = make_awaiting_payment()
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 1000 * denoms.ether
        self.pp.add(p1)
        self.pp.add(p2)
        self.assertTrue(self.pp.sendout())
        self.sci.batch_transfer.assert_called_once_with([p1, p2], mock.ANY)

    def test_closure_time(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 1000 * denoms.ether

        p1 = make_awaiting_payment()
        p2 = make_awaiting_payment()
        p5 = make_awaiting_payment()
        with freeze_time(timestamp_to_datetime(1)):
            self.pp.add(p1)
        with freeze_time(timestamp_to_datetime(2)):
            self.pp.add(p2)
        with freeze_time(timestamp_to_datetime(5)):
            self.pp.add(p5)

        self.pp.deadline = 0

        closure_time = 2
        time_value = closure_time + self.pp.CLOSURE_TIME_DELAY
        with freeze_time(timestamp_to_datetime(time_value)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p1, p2],
                closure_time)
            self.sci.batch_transfer.reset_mock()

        closure_time = 4
        time_value = closure_time + self.pp.CLOSURE_TIME_DELAY
        with freeze_time(timestamp_to_datetime(time_value)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_not_called()
            self.sci.batch_transfer.reset_mock()

        closure_time = 6
        time_value = closure_time + self.pp.CLOSURE_TIME_DELAY
        with freeze_time(timestamp_to_datetime(time_value)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p5],
                closure_time)
            self.sci.batch_transfer.reset_mock()

    def test_short_on_gnt(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 4 * denoms.ether
        self.pp.deadline = 0
        self.pp.CLOSURE_TIME_DELAY = 0

        p1 = make_awaiting_payment(value=1 * denoms.ether, ts=1)
        p2 = make_awaiting_payment(value=2 * denoms.ether, ts=2)
        p5 = make_awaiting_payment(value=5 * denoms.ether, ts=3)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p5)

        with freeze_time(timestamp_to_datetime(10)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p1, p2],
                10)
            self.sci.batch_transfer.reset_mock()

        self.sci.get_gntw_balance.return_value = 5 * denoms.ether
        self.pp.gnt_balance(refresh=True)
        with freeze_time(timestamp_to_datetime(10)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p5],
                10)
            self.sci.batch_transfer.reset_mock()

    def test_short_on_gnt_closure_time(self):
        self.sci.get_eth_balance.return_value = denoms.ether
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 4 * denoms.ether
        self.pp.deadline = 0
        self.pp.CLOSURE_TIME_DELAY = 0

        p1 = make_awaiting_payment(value=1 * denoms.ether, ts=1)
        p2 = make_awaiting_payment(value=2 * denoms.ether, ts=2)
        p5 = make_awaiting_payment(value=5 * denoms.ether, ts=2)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p5)

        with freeze_time(timestamp_to_datetime(10)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p1],
                10)
            self.sci.batch_transfer.reset_mock()

        self.sci.get_gntw_balance.return_value = 10 * denoms.ether
        self.pp.gnt_balance(refresh=True)
        with freeze_time(timestamp_to_datetime(10)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p2, p5],
                10)
            self.sci.batch_transfer.reset_mock()

    def test_short_on_eth(self):
        self.sci.get_eth_balance.return_value = self.sci.GAS_PRICE * \
            (self.sci.GAS_BATCH_PAYMENT_BASE + 2 * self.sci.GAS_PER_PAYMENT)
        self.sci.get_gnt_balance.return_value = 0
        self.sci.get_gntw_balance.return_value = 1000 * denoms.ether
        self.pp.deadline = 0
        self.pp.CLOSURE_TIME_DELAY = 0

        p1 = make_awaiting_payment(value=1, ts=1)
        p2 = make_awaiting_payment(value=2, ts=2)
        p5 = make_awaiting_payment(value=5, ts=3)
        self.pp.add(p1)
        self.pp.add(p2)
        self.pp.add(p5)

        with freeze_time(timestamp_to_datetime(10)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p1, p2],
                10)
            self.sci.batch_transfer.reset_mock()

        self.sci.get_eth_balance.return_value = denoms.ether
        self.pp.eth_balance(refresh=True)
        with freeze_time(timestamp_to_datetime(10)):
            self.pp.sendout()
            self.sci.batch_transfer.assert_called_with(
                [p5],
                10)
            self.sci.batch_transfer.reset_mock()


class FaucetTest(unittest.TestCase):
    @patch('requests.get')
    def test_error_code(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 500
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @patch('requests.get')
    def test_error_msg(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 0, 'message': "Ooops!"}
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @patch('requests.get')
    def test_success(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 1486605259,
                                      'amount': 999999999999999}
        get.return_value = response
        assert tETH_faucet_donate(addr) is True
        assert get.call_count == 1
        assert encode_hex(addr)[2:] in get.call_args[0][0]
