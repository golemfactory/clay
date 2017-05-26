import mock
import random
import time
import unittest
import requests
from os import urandom

from mock import patch, Mock

from twisted.internet.task import Clock

from ethereum import tester
from ethereum.keys import privtoaddr
from ethereum.processblock import apply_transaction
from ethereum.transactions import Transaction
from ethereum.utils import denoms
from rlp.utils import decode_hex

from golem.ethereum import Client
from golem.ethereum.node import Faucet
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.ethereum.contracts import TestGNT
from golem.model import Payment, PaymentStatus
from golem.testutils import DatabaseFixture

SYNC_TEST_INTERVAL = 0.01


def wait_for(condition, timeout, step=0.1):
    for _ in xrange(int(timeout / step)):
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
        self.client.get_balance.return_value = 0
        self.client.send.side_effect = lambda tx: "0x" + tx.hash.encode('hex')
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
        addr_hex = '0x' + self.addr.encode('hex')
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
        addr_hex = '0x' + self.addr.encode('hex')
        self.client.get_balance.assert_called_once_with(addr_hex)
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_eth_balance_refresh_increase(self):
        expected_balance = random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        addr_hex = '0x' + self.addr.encode('hex')
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
        addr_hex = '0x' + self.addr.encode('hex')
        self.client.get_balance.assert_called_once_with(addr_hex)

        expected_balance -= random.randint(0, expected_balance)
        assert expected_balance >= 0
        self.client.get_balance.return_value = expected_balance
        b = self.pp.eth_balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_available_eth_zero(self):
        assert self.pp._eth_available() == 0

    def test_available_eth_nonzero(self):
        eth = random.randint(0, 10 * denoms.ether)
        self.client.get_balance.return_value = eth
        assert self.pp._eth_available() == eth

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
        self.client.get_balance.assert_called_once_with('0x' + self.addr.encode('hex'))

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
        self.addr.encode('hex') in get.call_args[0][0]

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

        for c in combinations:
            print("Subtest {}".format(c))
            # Allow reseting the status.
            time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
            self.client.get_peer_count.return_value = 0
            self.client.is_syncing.return_value = False
            assert not pp.synchronized()
            time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
            self.client.get_peer_count.return_value = c[0]
            self.client.is_syncing.return_value = c[1]
            assert not pp.synchronized()  # First time is always no.
            time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
            assert pp.synchronized() == (c[0] and not c[1])
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
        assert not pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 1
        self.client.is_syncing.return_value = syncing_status
        assert not pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert not pp.synchronized()

        self.client.get_peer_count.return_value = 1
        self.client.is_syncing.return_value = False
        assert not pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert not pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 0
        self.client.is_syncing.return_value = False
        assert not pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 2
        self.client.is_syncing.return_value = False
        assert not pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        self.client.get_peer_count.return_value = 2
        self.client.is_syncing.return_value = syncing_status
        assert not pp.synchronized()
        PaymentProcessor.SYNC_CHECK_INTERVAL = I

    def test_monitor_progress(self):
        a1 = urandom(20)

        inprogress = self.pp._inprogress

        # Give 1 ETH and 99 GNT
        balance_eth = 1 * denoms.ether
        balance_gnt = 99 * denoms.ether
        self.client.get_balance.return_value = balance_eth
        self.client.call.return_value = hex(balance_gnt)[:-1]  # Skip L suffix.

        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gnt
        assert self.pp._eth_reserved() == 0
        assert self.pp._eth_available() == balance_eth

        gnt_value = 10**17
        p = Payment.create(subtask="p1", payee=a1, value=gnt_value)
        assert self.pp.add(p)
        assert self.pp._gnt_reserved() == gnt_value
        assert self.pp._gnt_available() == balance_gnt - gnt_value
        assert self.pp._eth_reserved() == PaymentProcessor.SINGLE_PAYMENT_ETH_COST
        assert self.pp._eth_available() == balance_eth - PaymentProcessor.SINGLE_PAYMENT_ETH_COST

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
        self.client.call.return_value = hex(balance_gnt - gnt_value)[:-1]  # Skip L suffix.
        self.pp.monitor_progress()
        assert len(inprogress) == 1
        assert tx.hash in inprogress
        assert inprogress[tx.hash] == [p]
        assert self.pp.gnt_balance(True) == balance_gnt - gnt_value
        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gnt - gnt_value
        assert self.pp._eth_reserved() == PaymentProcessor.SINGLE_PAYMENT_ETH_COST
        assert self.pp._eth_available() == balance_eth - PaymentProcessor.SINGLE_PAYMENT_ETH_COST

        self.pp.monitor_progress()
        assert len(inprogress) == 1
        assert self.pp._gnt_reserved() == 0
        assert self.pp._gnt_available() == balance_gnt - gnt_value
        assert self.pp._eth_reserved() == PaymentProcessor.SINGLE_PAYMENT_ETH_COST
        assert self.pp._eth_available() == balance_eth - PaymentProcessor.SINGLE_PAYMENT_ETH_COST

        receipt = {'blockNumber': 8214, 'blockHash': '0x' + 64*'f', 'gasUsed': 55001}
        self.client.get_transaction_receipt.return_value = receipt
        self.pp.monitor_progress()
        assert len(inprogress) == 0
        assert p.status == PaymentStatus.confirmed
        assert p.details['block_number'] == 8214
        assert p.details['block_hash'] == 64*'f'
        assert p.details['fee'] == 55001 * self.pp.GAS_PRICE
        assert self.pp._gnt_reserved() == 0


class PaymentProcessorFunctionalTest(DatabaseFixture):
    """ In this suite we test Ethereum state changes done by PaymentProcessor.
    """
    def setUp(self):
        DatabaseFixture.setUp(self)
        self.state = tester.state()
        gnt_addr = self.state.evm(decode_hex(TestGNT.INIT_HEX))
        self.state.mine()
        self.gnt = tester.ABIContract(self.state, TestGNT.ABI, gnt_addr)
        PaymentProcessor.TESTGNT_ADDR = gnt_addr
        self.privkey = tester.k1
        self.client = mock.MagicMock(spec=Client)
        self.client.get_peer_count.return_value = 0
        self.client.is_syncing.return_value = False
        self.client.get_transaction_count.side_effect = \
            lambda addr: self.state.block.get_nonce(decode_hex(addr[2:]))
        self.client.get_balance.side_effect = \
            lambda addr: self.state.block.get_balance(decode_hex(addr[2:]))

        def call(_from, to, data, **kw):
            # pyethereum does not have direct support for non-mutating calls.
            # The implemenation just copies the state and discards it after.
            # Here we apply real transaction, but with gas price 0.
            # We assume the transaction does not modify the state, but nonce
            # will be bumped no matter what.
            _from = _from[2:].decode('hex')
            data = data[2:].decode('hex')
            nonce = self.state.block.get_nonce(_from)
            value = kw.get('value', 0)
            tx = Transaction(nonce, 0, 100000, to, value, data)
            assert _from == tester.a1
            tx.sign(tester.k1)
            block = kw['block']
            assert block == 'pending'
            success, output = apply_transaction(self.state.block, tx)
            assert success
            return '0x' + output.encode('hex')

        def send(tx):
            success, _ = apply_transaction(self.state.block, tx)
            assert success  # What happens in real RPC eth_send?
            return '0x' + tx.hash.encode('hex')

        self.client.call.side_effect = call
        self.client.send.side_effect = send
        self.pp = PaymentProcessor(self.client, self.privkey)
        self.clock = Clock()
        self.pp._loopingCall.clock = self.clock

    def test_initial_eth_balance(self):
        # ethereum.tester assigns this amount to predefined accounts.
        assert self.pp.eth_balance() == 1000000000000000000000000

    def check_synchronized(self):
        assert not self.pp.synchronized()
        self.client.get_peer_count.return_value = 1
        assert not self.pp.synchronized()
        I = PaymentProcessor.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        assert self.pp.SYNC_CHECK_INTERVAL == SYNC_TEST_INTERVAL
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert not self.pp.synchronized()
        time.sleep(1.5 * PaymentProcessor.SYNC_CHECK_INTERVAL)
        assert self.pp.synchronized()
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
        self.pp.synchronized = lambda *_: True
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
        value = b / 5 - 100
        for i in range(5):
            subtask_id = 's{}'.format(i)
            p = Payment.create(subtask=subtask_id, payee=payee, value=value)
            assert self.pp.add(p)

        q = Payment.create(subtask='F', payee=payee, value=value)
        assert not self.pp.add(q)
