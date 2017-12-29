import json
import random
import time
import unittest
import rlp
from os import urandom

import mock
import requests
from ethereum import tester, processblock
from ethereum.processblock import apply_transaction
from ethereum.transactions import Transaction
from ethereum.utils import denoms, privtoaddr
from freezegun import freeze_time
from mock import patch, Mock
from twisted.internet.task import Clock

from golem.core.common import timestamp_to_datetime
from golem.ethereum import Client
from golem.ethereum.contracts import TestGNT
from golem.ethereum.node import Faucet
from golem.ethereum.paymentprocessor import \
    PaymentProcessor, GNTToken, GNTWToken, encode_payments
from golem.model import Payment, PaymentStatus
from golem.testutils import DatabaseFixture
from golem.utils import encode_hex, decode_hex

SYNC_TEST_INTERVAL = 0.01
TEST_GNT_ABI = json.loads(TestGNT.ABI)

# FIXME: upgrade to pyethereum 2.x
setattr(processblock, 'unicode', str)


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
        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        self.client = mock.MagicMock(spec=Client)
        self.client.web3 = mock.MagicMock()
        self.client.get_balance.return_value = 0
        self.client.send.side_effect = lambda tx: '0x' + encode_hex(tx.hash)
        self.nonce = random.randint(0, 9999)
        self.client.get_transaction_count.return_value = self.nonce
        # FIXME: PaymentProcessor should be started and stopped!
        self.pp = PaymentProcessor(self.client, self.privkey)
        self.pp._loopingCall.clock = Clock()  # Disable looping call.

    def test_eth_balance(self):
        expected_balance = random.randint(0, 2**128 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance()
        assert b == expected_balance
        b = self.pp.eth_balance()
        assert b == expected_balance
        addr_hex = '0x' + encode_hex(self.addr)
        self.client.get_balance.assert_called_once_with(addr_hex)

    def test_gnt_balance(self):
        expected_balance = random.randint(0, 2**128 - 1)
        v = '0x{:x}'.format(expected_balance)
        self.client.call.return_value = v
        b = self.pp.gnt_balance()
        assert b == expected_balance
        self.client.call.return_value = '0xaa'
        b = self.pp.gnt_balance()
        assert b == expected_balance
        self.client.call.assert_called_once()

    def test_eth_balance_refresh(self):
        expected_balance = random.randint(0, 2**128 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance()
        assert b == expected_balance
        addr_hex = '0x' + encode_hex(self.addr)
        self.client.get_balance.assert_called_once_with(addr_hex)
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_eth_balance_refresh_increase(self):
        expected_balance = random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        addr_hex = '0x' + encode_hex(self.addr)
        self.client.get_balance.assert_called_once_with(addr_hex)

        expected_balance += random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        assert self.pp.eth_balance() == b
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_balance_refresh_decrease(self):
        expected_balance = random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        addr_hex = '0x' + encode_hex(self.addr)
        self.client.get_balance.assert_called_once_with(addr_hex)

        expected_balance -= random.randint(0, expected_balance)
        assert expected_balance >= 0
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_available_eth_zero(self):
        assert self.pp._eth_available() == \
            -PaymentProcessor.ETH_BATCH_PAYMENT_BASE

    def test_available_eth_nonzero(self):
        eth = random.randint(1, 10 * denoms.ether)
        self.client.get_balance.return_value = eth
        eth_available = eth - PaymentProcessor.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == eth_available

    def test_add_failure(self):
        a1 = urandom(20)
        a2 = urandom(20)
        p1 = Payment.create(subtask="p1", payee=a1, value=1)
        p2 = Payment.create(subtask="p2", payee=a2, value=2)

        assert p1.status is PaymentStatus.awaiting
        assert p2.status is PaymentStatus.awaiting

        self.client.get_balance.return_value = 0
        assert self.pp.add(p1) is False
        assert self.pp.add(p2) is False
        addr_hex = '0x' + encode_hex(self.addr)
        self.client.get_balance.assert_called_once_with(addr_hex)

        assert p1.status is PaymentStatus.awaiting
        assert p2.status is PaymentStatus.awaiting

    def test_add_invalid_payment_status(self):
        a1 = urandom(20)
        p1 = Payment.create(subtask="p1", payee=a1, value=1, status=PaymentStatus.confirmed)
        assert p1.status is PaymentStatus.confirmed

        with self.assertRaises(RuntimeError):
            self.pp.add(p1)

    @patch('requests.get')
    def test_faucet(self, get):
        response = Mock(spec=requests.Response)
        response.status_code = 200
        pp = PaymentProcessor(self.client, self.privkey, faucet=True)
        pp.get_ether_from_faucet()
        assert get.call_count == 1
        assert encode_hex(self.addr) in get.call_args[0][0]

    def test_gnt_faucet(self):
        self.client.call.return_value = '0x00'
        pp = PaymentProcessor(self.client, self.privkey, faucet=True)
        pp.get_gnt_from_faucet()
        assert self.client.send.call_count == 1
        tx = self.client.send.call_args[0][0]
        assert tx.nonce == self.nonce
        assert len(tx.data) == 4

    def test_faucet_gimme_money(self):
        assert self.pp.eth_balance() == 0
        value = 12 * denoms.ether
        Faucet.gimme_money(self.client, self.addr, value)

    def test_payment_aggregation(self):
        a1 = urandom(20)
        a2 = urandom(20)
        a3 = urandom(20)

        self.client.get_balance.return_value = 100 * denoms.ether
        self.client.call.return_value = hex(100 * denoms.ether)[:-1]

        assert self.pp.add(Payment.create(subtask="p1", payee=a1, value=1))
        assert self.pp.add(Payment.create(subtask="p2", payee=a2, value=1))
        assert self.pp.add(Payment.create(subtask="p3", payee=a2, value=1))
        assert self.pp.add(Payment.create(subtask="p4", payee=a3, value=1))
        assert self.pp.add(Payment.create(subtask="p5", payee=a3, value=1))
        assert self.pp.add(Payment.create(subtask="p6", payee=a3, value=1))

        self.pp.deadline = int(time.time())
        assert self.pp.sendout()
        assert self.client.send.call_count == 1
        tx = self.client.send.call_args[0][0]
        assert tx.value == 0
        assert len(tx.data) == 4 + 2*32 + 3*32  # Id + array abi + bytes32[3]

    def test_payment_deadline(self):
        a1 = urandom(20)
        a2 = urandom(20)
        a3 = urandom(20)

        self.client.get_balance.return_value = 100 * denoms.ether
        self.client.call.return_value = hex(100 * denoms.ether)[:-1]

        now = int(time.time())
        assert self.pp.add(Payment.create(subtask="p1", payee=a1, value=1))
        assert check_deadline(self.pp.deadline, now + self.pp.DEFAULT_DEADLINE)

        assert self.pp.add(Payment.create(subtask="p2", payee=a2, value=1), deadline=20000)
        assert check_deadline(self.pp.deadline, now + self.pp.DEFAULT_DEADLINE)

        assert self.pp.add(Payment.create(subtask="p3", payee=a2, value=1), deadline=1)
        assert check_deadline(self.pp.deadline, now + 1)

        assert self.pp.add(Payment.create(subtask="p4", payee=a3, value=1))
        assert check_deadline(self.pp.deadline, now + 1)

        assert self.pp.add(Payment.create(subtask="p5", payee=a3, value=1), deadline=1)
        assert check_deadline(self.pp.deadline, now + 1)

        assert self.pp.add(Payment.create(subtask="p6", payee=a3, value=1), deadline=0)
        assert check_deadline(self.pp.deadline, now)

        assert self.pp.add(Payment.create(subtask="p7", payee=a3, value=1), deadline=-1)
        assert check_deadline(self.pp.deadline, now - 1)

    def test_payment_deadline_not_reached(self):
        a1 = urandom(20)

        self.client.get_balance.return_value = 100 * denoms.ether
        self.client.call.return_value = hex(100 * denoms.ether)[:-1]

        now = int(time.time())
        inf = now + 12*30*24*60*60
        deadline = self.pp.deadline
        assert self.pp.deadline > inf
        assert not self.pp.sendout()
        assert self.pp.deadline == deadline

        p = Payment.create(subtask="p1", payee=a1, value=1111)
        assert self.pp.add(p, deadline=1111)
        assert check_deadline(self.pp.deadline, now + 1111)
        assert not self.pp.sendout()
        assert check_deadline(self.pp.deadline, now + 1111)

    def test_wait_until_synchronized(self):
        PaymentProcessor.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        pp = PaymentProcessor(self.client, self.privkey, faucet=False)

        self.client.get_peer_count.return_value = 4
        self.client.is_syncing.return_value = False
        self.assertTrue( pp.wait_until_synchronized())

    def test_synchronized(self):
        I = PaymentProcessor.SYNC_CHECK_INTERVAL
        PaymentProcessor.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        pp = PaymentProcessor(self.client, self.privkey, faucet=False)
        syncing_status = {'startingBlock': '0x384',
                          'currentBlock': '0x386',
                          'highestBlock': '0x454'}
        combinations = ((0, False),
                        (0, syncing_status),
                        (1, False),
                        (1, syncing_status),
                        (65, syncing_status),
                        (65, False))

        self.client.web3.eth.syncing.return_value=\
            {'currentBlock': 123, 'highestBlock': 1234}

        for c in combinations:
            print("Subtest {}".format(c))
            # Allow reseting the status.
            time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
            self.client.get_peer_count.return_value = 0
            self.client.is_syncing.return_value = False
            assert not pp.is_synchronized()
            time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
            self.client.get_peer_count.return_value = c[0]
            self.client.is_syncing.return_value = c[1]
            assert not pp.is_synchronized()  # First time is always no.
            time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
            assert pp.is_synchronized() == (c[0] and not c[1])
        PaymentProcessor.SYNC_CHECK_INTERVAL = I

    def test_synchronized_unstable(self):
        I = PaymentProcessor.SYNC_CHECK_INTERVAL
        PaymentProcessor.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        pp = PaymentProcessor(self.client, self.privkey, faucet=False)
        syncing_status = {'startingBlock': '0x0',
                          'currentBlock': '0x1',
                          'highestBlock': '0x4096'}

        self.client.get_peer_count.return_value = 1
        self.client.is_syncing.return_value = False
        assert not pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 1
        self.client.is_syncing.return_value = syncing_status
        assert not pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert not pp.is_synchronized()

        self.client.get_peer_count.return_value = 1
        self.client.is_syncing.return_value = False
        assert not pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert not pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 0
        self.client.is_syncing.return_value = False
        assert not pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 2
        self.client.is_syncing.return_value = False
        assert not pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 2
        self.client.is_syncing.return_value = syncing_status
        assert not pp.is_synchronized()
        PaymentProcessor.SYNC_CHECK_INTERVAL = I

    def test_monitor_progress(self):
        inprogress = self.pp._inprogress

        # Give 1 ETH and 99 GNT
        balance_eth = 1 * denoms.ether
        balance_gnt = 99 * denoms.ether
        self.client.get_balance.return_value = balance_eth
        self.client.call.return_value = hex(balance_gnt)

        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gnt
        assert self.pp._eth_reserved() == \
            PaymentProcessor.ETH_BATCH_PAYMENT_BASE
        eth_available = balance_eth - PaymentProcessor.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == eth_available

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=urandom(20), value=gnt_value)
        assert self.pp.add(p)
        assert self.pp._gnt_reserved() == gnt_value
        assert self.pp._gnt_available() == balance_gnt - gnt_value
        eth_reserved = PaymentProcessor.ETH_BATCH_PAYMENT_BASE + \
            1 * PaymentProcessor.ETH_PER_PAYMENT
        assert self.pp._eth_reserved() == eth_reserved
        eth_available = balance_eth - eth_reserved
        assert self.pp._eth_available() == eth_available

        self.pp.deadline = int(time.time())
        assert self.pp.sendout()
        assert self.client.send.call_count == 1
        tx = self.client.send.call_args[0][0]
        assert tx.value == 0
        assert len(tx.data) == 4 + 2*32 + 32  # Id + array abi + bytes32[1]

        assert len(inprogress) == 1
        assert tx.hash in inprogress
        assert inprogress[tx.hash] == [p]

        # Check payment status in the Blockchain
        self.client.get_transaction_receipt.return_value = None
        self.client.call.return_value = hex(balance_gnt - gnt_value)
        self.pp.monitor_progress()
        balance_eth_after_sendout = balance_eth - \
            PaymentProcessor.ETH_BATCH_PAYMENT_BASE - \
            1 * PaymentProcessor.ETH_PER_PAYMENT
        self.client.get_balance.return_value = balance_eth_after_sendout
        assert len(inprogress) == 1
        assert tx.hash in inprogress
        assert inprogress[tx.hash] == [p]
        assert self.pp.gnt_balance(True) == balance_gnt - gnt_value
        assert self.pp.eth_balance(True) == balance_eth_after_sendout
        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gnt - gnt_value
        assert self.pp._eth_reserved() == \
            PaymentProcessor.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == \
            balance_eth_after_sendout - PaymentProcessor.ETH_BATCH_PAYMENT_BASE

        self.pp.monitor_progress()
        assert len(inprogress) == 1
        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gnt - gnt_value
        assert self.pp._eth_reserved() == \
            PaymentProcessor.ETH_BATCH_PAYMENT_BASE
        assert self.pp._eth_available() == \
            balance_eth_after_sendout - PaymentProcessor.ETH_BATCH_PAYMENT_BASE

        tx_block_number = 1337
        self.client.get_block_number.return_value = tx_block_number
        receipt = {
            'blockNumber': tx_block_number,
            'blockHash': '0x' + 64*'f',
            'gasUsed': 55001,
            'status': '0x1',
        }
        self.client.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 1)

        self.client.get_block_number.return_value =\
            tx_block_number + self.pp.REQUIRED_CONFIRMATIONS
        self.client.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.confirmed)
        self.assertEqual(p.details.block_number, tx_block_number)
        self.assertEqual(p.details.block_hash, 64*'f')
        self.assertEqual(p.details.fee, 55001 * self.pp.GAS_PRICE)
        self.assertEqual(self.pp._gnt_reserved(), 0)

    def test_failed_transaction(self):
        inprogress = self.pp._inprogress

        balance_eth = 1 * denoms.ether
        balance_gnt = 99 * denoms.ether
        self.client.get_balance.return_value = balance_eth
        self.client.call.return_value = hex(balance_gnt)

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=urandom(20), value=gnt_value)
        assert self.pp.add(p)

        self.pp.deadline = int(time.time())
        assert self.pp.sendout()
        tx = self.client.send.call_args[0][0]

        # Check payment status in the Blockchain
        self.client.get_transaction_receipt.return_value = None
        self.client.call.return_value = hex(balance_gnt - gnt_value)

        tx_block_number = 1337
        receipt = {
            'blockNumber': tx_block_number,
            'blockHash': '0x' + 64*'f',
            'gasUsed': 55001,
            'status': '0x0',
        }
        self.client.get_block_number.return_value = \
            tx_block_number + self.pp.REQUIRED_CONFIRMATIONS
        self.client.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.awaiting)

        self.pp.deadline = int(time.time())
        assert self.pp.sendout()
        self.assertEqual(len(inprogress), 1)
        tx = self.client.send.call_args[0][0]

        receipt['status'] = '0x1'
        self.client.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        self.assertEqual(len(inprogress), 0)
        self.assertEqual(p.status, PaymentStatus.confirmed)
        self.assertEqual(p.details.block_number, tx_block_number)
        self.assertEqual(p.details.block_hash, 64*'f')
        self.assertEqual(p.details.fee, 55001 * self.pp.GAS_PRICE)
        self.assertEqual(self.pp._gnt_reserved(), 0)

    def test_payment_timestamp(self):
        self.client.get_balance.return_value = denoms.ether
        self.client.call.return_value = hex(denoms.ether)

        ts = 7
        p = Payment.create(subtask="p1", payee=urandom(20), value=1)
        with freeze_time(timestamp_to_datetime(ts)):
            self.pp.add(p)
        self.assertEqual(ts, p.processed_ts)

        new_ts = 9
        with freeze_time(timestamp_to_datetime(new_ts)):
            self.pp.add(p)
        self.assertEqual(ts, p.processed_ts)


class PaymentProcessorFunctionalTest(DatabaseFixture):
    """ In this suite we test Ethereum state changes done by PaymentProcessor.
    """
    def setUp(self):
        DatabaseFixture.setUp(self)
        self.state = tester.state()
        gnt_evm_addr = self.state.evm(decode_hex(TestGNT.INIT_HEX))
        gnt_addr = encode_hex(gnt_evm_addr)
        print('gnt_addr %s', gnt_addr)
        self.state.mine()
        self.gnt = tester.ABIContract(self.state, TEST_GNT_ABI, gnt_addr)
        GNTToken.TESTGNT_ADDR = decode_hex(gnt_addr)
        self.privkey = tester.k1
        self.client = mock.MagicMock(spec=Client)
        self.client.get_peer_count.return_value = 0
        self.client.is_syncing.return_value = False
        self.client.get_transaction_count.side_effect = \
            lambda a: self.state.block.get_nonce(decode_hex(a))
        self.client.get_balance.side_effect = \
            lambda a: self.state.block.get_balance(decode_hex(a))

        def call(_from, to, data, **kw):
            # pyethereum does not have direct support for non-mutating calls.
            # The implementation just copies the state and discards it after.
            # Here we apply real transaction, but with gas price 0.
            # We assume the transaction does not modify the state, but nonce
            # will be bumped no matter what.
            _from = decode_hex(_from[2:])
            data = decode_hex(data[2:])
            nonce = self.state.block.get_nonce(_from)
            value = kw.get('value', 0)
            tx = Transaction(nonce, 0, 100000, to, value, data)
            assert _from == tester.a1
            tx.sign(tester.k1)
            block = kw['block']
            assert block == 'pending'
            success, output = apply_transaction(self.state.block, tx)
            assert success
            return '0x' + encode_hex(output)

        def send(tx):
            success, _ = apply_transaction(self.state.block, tx)
            assert success  # What happens in real RPC eth_send?
            return '0x' + encode_hex(tx.hash)

        self.client.call.side_effect = call
        self.client.send.side_effect = send
        self.pp = PaymentProcessor(self.client, self.privkey)
        self.clock = Clock()
        self.pp._loopingCall.clock = self.clock

    # FIXME: what is the purpose of this test?
    def test_initial_eth_balance(self):
        # ethereum.tester assigns this amount to predefined accounts.
        assert self.pp.eth_balance() == 1000000000000000000000000

    def check_synchronized(self):
        assert not self.pp.is_synchronized()
        self.client.get_peer_count.return_value = 1
        assert not self.pp.is_synchronized()
        I = PaymentProcessor.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        assert self.pp.SYNC_CHECK_INTERVAL == SYNC_TEST_INTERVAL
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert not self.pp.is_synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert self.pp.is_synchronized()
        PaymentProcessor.SYNC_CHECK_INTERVAL = I

    def test_synchronized(self):
        self.pp.start()
        self.check_synchronized()
        self.pp.stop()

    def test_gnt_faucet(self, *_):
        self.pp._PaymentProcessor__faucet = True
        self.pp._run()
        assert self.pp.eth_balance() > 0
        assert self.pp.gnt_balance() == 0
        self.check_synchronized()
        self.state.mine()
        self.clock.advance(60)
        self.pp._run()
        assert self.pp.gnt_balance(True) == 1000 * denoms.ether

    def test_single_payment(self, *_):
        self.pp._run()
        self.gnt.create(sender=self.privkey)
        self.state.mine()
        self.check_synchronized()
        assert self.pp.gnt_balance() == 1000 * denoms.ether

        payee = urandom(20)
        b = self.pp.gnt_balance()
        # FIXME: Big values does not fit into the database
        value = random.randint(0, b / 1000)
        p1 = Payment.create(subtask="p1", payee=payee, value=value)
        assert self.pp._gnt_available() == b
        assert self.pp._gnt_reserved() == 0
        self.pp.add(p1)
        assert self.pp._gnt_available() == b - value
        assert self.pp._gnt_reserved() == value

        # Sendout.
        self.pp.deadline = int(time.time())
        self.pp._run()
        assert self.pp.gnt_balance(True) == b - value
        assert self.pp._gnt_available() == b - value
        assert self.pp._gnt_reserved() == 0

        assert self.gnt.balanceOf(payee) == value
        assert self.gnt.balanceOf(tester.a1) == self.pp._gnt_available()

        # Confirm.
        assert self.pp.gnt_balance(True) == b - value
        assert self.pp._gnt_reserved() == 0

    def test_get_ether(self, *_):
        def exception(*_):
            raise Exception

        def failure(*_):
            return False

        def success(*_):
            return True

        self.pp.monitor_progress = Mock()
        self.pp.is_synchronized = lambda *_: True
        self.pp.sendout = Mock()

        self.pp.get_gnt_from_faucet = failure
        self.pp.get_ether_from_faucet = failure

        self.pp._run()
        assert not self.pp._waiting_for_faucet
        assert not self.pp.monitor_progress.called
        assert not self.pp.sendout.called

        self.pp.get_ether_from_faucet = success

        self.pp._run()
        assert not self.pp._waiting_for_faucet
        assert not self.pp.monitor_progress.called
        assert not self.pp.sendout.called

        self.pp.get_gnt_from_faucet = success

        self.pp._run()
        assert not self.pp._waiting_for_faucet
        assert self.pp.monitor_progress.called
        assert self.pp.sendout.called

    def test_no_gnt_available(self):
        self.pp.start()
        self.gnt.create(sender=self.privkey)
        self.state.mine()
        self.check_synchronized()
        assert self.pp.gnt_balance() == 1000 * denoms.ether

        payee = urandom(20)
        b = self.pp.gnt_balance()
        value = int(b / 5 - 100)
        for i in range(5):
            subtask_id = 's{}'.format(i)
            p = Payment.create(subtask=subtask_id, payee=payee, value=value)
            assert self.pp.add(p)

        q = Payment.create(subtask='F', payee=payee, value=value)
        assert not self.pp.add(q)

    def test_balance_value(self):
        now = time.time()
        dt = self.pp.BALANCE_RESET_TIMEOUT * 2
        valid_value = 10 * denoms.ether

        assert self.pp._balance_value(valid_value, 0) is valid_value
        assert self.pp._balance_value(valid_value, now + 10) is valid_value
        assert self.pp._balance_value(None, 0) == 0
        assert self.pp._balance_value(None, now - dt) == 0
        assert self.pp._balance_value(None, now) is None


def make_awaiting_payment(value=None):
    p = mock.Mock()
    p.status = PaymentStatus.awaiting
    p.payee = urandom(20)
    p.value = value if value else random.randint(1, 10)
    p.subtask = '123'
    return p


class InteractionWithTokenTest(DatabaseFixture):

    def setUp(self):
        DatabaseFixture.setUp(self)
        self.token = mock.Mock()
        self.privkey = urandom(32)
        self.client = mock.Mock()

        def token_factory(*_):
            return self.token

        self.pp = PaymentProcessor(self.client,
                                   self.privkey,
                                   token_factory=token_factory)

    def test_faucet(self):
        self.pp._PaymentProcessor__faucet = True

        self.token.get_balance.return_value = 1000 * denoms.ether
        self.assertTrue(self.pp.get_gnt_from_faucet())
        self.token.request_from_faucet.assert_not_called()

        self.token.get_balance.return_value = 0
        self.assertFalse(self.pp.get_gnt_from_faucet())
        self.token.request_from_faucet.assert_called_with(self.privkey)

    def test_batch_transfer(self):
        self.pp.deadline = time.time() - 1
        self.token.batch_transfer.return_value = None
        self.assertFalse(self.pp.sendout())

        p1 = make_awaiting_payment()
        p2 = make_awaiting_payment()
        self.client.get_balance.return_value = denoms.ether
        self.token.get_balance.return_value = 1000 * denoms.ether
        self.pp.add(p1)
        self.pp.add(p2)
        tx = mock.Mock()
        tx_hash = '0xdead'
        tx.hash = decode_hex(tx_hash)
        self.client.send.return_value = tx_hash
        self.token.batch_transfer.return_value = tx
        self.assertTrue(self.pp.sendout())
        self.client.send.assert_called_with(tx)

    def test_get_incomes_from_block(self):
        block_number = 1
        receiver_address = '0xbadcode'
        some_address = '0xdeadbeef'

        expected_incomes = [{'sender': some_address, 'value': 1}]
        self.token.get_incomes_from_block.return_value = expected_incomes
        incomes = self.pp.get_incomes_from_block(block_number, receiver_address)
        self.assertEqual(expected_incomes, incomes)


class GNTTokenTest(unittest.TestCase):
    def setUp(self):
        self.client = mock.Mock()
        self.privkey = urandom(32)
        self.addr = '0x' + encode_hex(privtoaddr(self.privkey))
        self.token = GNTToken(self.client)

    def test_get_balance(self):
        abi = mock.Mock()
        self.token._GNTToken__testGNT = abi
        encoded_data = 'dada'
        abi.encode_function_call.return_value = encoded_data

        self.client.call.return_value = None
        self.assertEqual(None, self.token.get_balance(self.addr))
        abi.encode_function_call.assert_called_with(
            'balanceOf',
            [privtoaddr(self.privkey)])
        self.client.call.assert_called_with(
            _from=mock.ANY,
            to='0x' + encode_hex(self.token.TESTGNT_ADDR),
            data='0x' + encode_hex(encoded_data),
            block='pending')

        self.client.call.return_value = '0x'
        self.assertEqual(0, self.token.get_balance(self.addr))

        self.client.call.return_value = '0xf'
        self.assertEqual(15, self.token.get_balance(self.addr))

    def test_batches(self):
        p1 = make_awaiting_payment()
        p2 = make_awaiting_payment()
        p3 = make_awaiting_payment()

        nonce = 0
        self.client.get_transaction_count.return_value = nonce

        abi = mock.Mock()
        self.token._GNTToken__testGNT = abi
        encoded_data = 'dada'
        abi.encode_function_call.return_value = encoded_data

        tx = self.token.batch_transfer(self.privkey, [p1, p2, p3])
        self.assertEqual(nonce, tx.nonce)
        self.assertEqual(self.token.TESTGNT_ADDR, tx.to)
        self.assertEqual(0, tx.value)
        expected_gas = PaymentProcessor.GAS_BATCH_PAYMENT_BASE + \
            3 * PaymentProcessor.GAS_PER_PAYMENT
        self.assertEqual(expected_gas, tx.startgas)
        self.assertEqual(encoded_data, tx.data)
        abi.encode_function_call.assert_called_with(
            'batchTransfer',
            [encode_payments([p1, p2, p3])])

    def test_get_incomes_from_block(self):
        block_number = 1
        receiver_address = '0xbadcode'
        some_address = '0xdeadbeef'

        self.client.get_logs.return_value = None
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(None, incomes)

        topics = [self.token.TRANSFER_EVENT_ID, None, receiver_address]
        self.client.get_logs.assert_called_with(
            block_number,
            block_number,
            '0x' + encode_hex(self.token.TESTGNT_ADDR),
            topics)

        self.client.get_logs.return_value = [{
            'topics': ['0x0', some_address, receiver_address],
            'data': '0xf',
        }]
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(1, len(incomes))
        self.assertEqual(some_address, incomes[0]['sender'])
        self.assertEqual(15, incomes[0]['value'])


def abi_encoder(function_name, args):
    def bytes2hex(elem):
        if isinstance(elem, bytes):
            return encode_hex(elem)
        if isinstance(elem, list):
            for i, e in enumerate(elem):
                elem[i] = bytes2hex(e)
        return elem

    args = bytes2hex(args.copy())
    res = json.dumps({'function_name': function_name, 'args': args})
    return res


class GNTWTokenTest(unittest.TestCase):
    def setUp(self):
        self.client = mock.Mock()
        self.privkey = urandom(32)
        self.addr = '0x' + encode_hex(privtoaddr(self.privkey))
        self.token = GNTWToken(self.client)

        gnt_abi = mock.Mock()
        gnt_abi.encode_function_call.side_effect = abi_encoder
        self.token._GNTWToken__gnt = gnt_abi

        gntw_abi = mock.Mock()
        gntw_abi.encode_function_call.side_effect = abi_encoder
        self.token._GNTWToken__gntw = gntw_abi

        self.balances = {
            'gnt': None,
            'gntw': None,
        }

        self.pda = bytearray(32)
        self.pda_create_called = False

        def client_call(_from, to, data, block):
            self.assertEqual('pending', block)
            token_addr = decode_hex(to)
            data = json.loads(decode_hex(data).decode())
            if data['function_name'] == 'balanceOf':
                self.assertEqual(1, len(data['args']))

                if privtoaddr(self.privkey) == decode_hex(data['args'][0]):
                    if token_addr == self.token.TESTGNT_ADDRESS:
                        return self.balances['gnt']
                    if token_addr == self.token.GNTW_ADDRESS:
                        return self.balances['gntw']

                raise Exception('Unknown balance')

            if data['function_name'] == 'getPersonalDepositAddress':
                self.assertEqual(self.token.GNTW_ADDRESS, token_addr)
                self.assertEqual(1, len(data['args']))
                self.assertEqual(
                    privtoaddr(self.privkey),
                    decode_hex(data['args'][0]))
                return '0x' + encode_hex(self.pda)

            raise Exception('Unknown call {}'.format(data['function_name']))

        self.nonce = 0
        self.process_deposit_called = False
        self.transfer_called = False

        def client_send(tx):
            token_addr = tx.to
            data = json.loads(tx.data)
            self.assertEqual(self.nonce, tx.nonce)
            self.nonce += 1
            if data['function_name'] == 'createPersonalDepositAddress':
                self.assertEqual(self.token.GNTW_ADDRESS, token_addr)
                self.assertEqual(0, len(data['args']))
                self.assertEqual(
                    self.token.CREATE_PERSONAL_DEPOSIT_GAS,
                    tx.startgas)
                self.pda_create_called = True
                return '0x' + encode_hex(urandom(32))

            if data['function_name'] == 'transfer':
                self.assertEqual(self.token.TESTGNT_ADDRESS, token_addr)
                self.assertEqual(2, len(data['args']))
                self.assertEqual(encode_hex(self.pda[-20:]), data['args'][0])
                self.assertEqual(int(self.balances['gnt'], 16), data['args'][1])
                self.transfer_called = True
                return '0x' + encode_hex(urandom(32))

            if data['function_name'] == 'processDeposit':
                self.assertEqual(self.token.GNTW_ADDRESS, token_addr)
                self.assertEqual(0, len(data['args']))
                self.process_deposit_called = True
                return '0x' + encode_hex(urandom(32))

            raise Exception('Unknown send {}'.format(data['function_name']))

        self.client.call.side_effect = client_call
        self.client.send.side_effect = client_send
        self.client.get_transaction_count.side_effect = lambda *_: self.nonce

    def test_get_balance(self):
        self.assertEqual(None, self.token.get_balance(self.addr))

        self.balances['gnt'] = '0x'
        self.assertEqual(None, self.token.get_balance(self.addr))

        self.balances['gntw'] = '0x'
        self.assertEqual(0, self.token.get_balance(self.addr))

        self.balances['gnt'] = '0xf'
        self.assertEqual(15, self.token.get_balance(self.addr))

        self.balances['gntw'] = '0xa'
        self.assertEqual(25, self.token.get_balance(self.addr))

    def test_batches_enough_gntw(self):
        p1 = make_awaiting_payment(1)
        p2 = make_awaiting_payment(2)
        p3 = make_awaiting_payment(3)

        self.balances['gnt'] = '0x0'
        self.balances['gntw'] = '0xf'

        tx = self.token.batch_transfer(self.privkey, [p1, p2, p3])
        self.assertEqual(self.nonce, tx.nonce)
        self.assertEqual(self.token.GNTW_ADDRESS, tx.to)
        self.assertEqual(0, tx.value)
        expected_gas = PaymentProcessor.GAS_BATCH_PAYMENT_BASE + \
            3 * PaymentProcessor.GAS_PER_PAYMENT
        self.assertEqual(expected_gas, tx.startgas)
        expected_data = abi_encoder(
            'batchTransfer',
            [encode_payments([p1, p2, p3]), int(time.time())])
        self.assertEqual(expected_data, tx.data)

    def test_batches_gnt_convertion(self):
        p1 = make_awaiting_payment(1)

        self.balances['gnt'] = '0x10'
        self.balances['gntw'] = '0x0'

        # Will need to convert GNT to GNTW
        tx = self.token.batch_transfer(self.privkey, [p1])
        self.assertEqual(None, tx)
        # Created personal deposit
        self.assertTrue(self.pda_create_called)
        self.pda_create_called = False
        # Waiting for personal deposit tx to be mined
        tx = self.token.batch_transfer(self.privkey, [p1])
        self.assertEqual(None, tx)
        self.assertFalse(self.pda_create_called)
        self.assertFalse(self.transfer_called)
        self.assertFalse(self.process_deposit_called)
        # Personal deposit tx mined, sending and processing deposit
        self.pda = urandom(32)
        tx = self.token.batch_transfer(self.privkey, [p1])
        self.assertEqual(None, tx)
        # 2 transactions to convert GNT to GNTW
        self.assertEqual(3, self.nonce)
        self.assertTrue(self.transfer_called)
        self.assertTrue(self.process_deposit_called)

    def test_get_incomes_from_block(self):
        block_number = 1
        receiver_address = '0xbadcode'
        some_address = '0xdeadbeef'

        self.client.get_logs.return_value = None
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(None, incomes)

        topics = [self.token.TRANSFER_EVENT_ID, None, receiver_address]
        self.client.get_logs.assert_called_with(
            block_number,
            block_number,
            '0x' + encode_hex(self.token.GNTW_ADDRESS),
            topics)

        self.client.get_logs.return_value = [{
            'topics': ['0x0', some_address, receiver_address],
            'data': '0xf',
        }]
        incomes = self.token.get_incomes_from_block(block_number,
                                                    receiver_address)
        self.assertEqual(1, len(incomes))
        self.assertEqual(some_address, incomes[0]['sender'])
        self.assertEqual(15, incomes[0]['value'])
