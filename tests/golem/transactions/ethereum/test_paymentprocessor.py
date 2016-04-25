import logging
import mock
import random
import time
import unittest
from os import path, urandom

from ethereum.keys import privtoaddr

from golem.ethereum.contracts import BankOfDeposit
from golem.ethereum import Client
from golem.ethereum.node import Faucet, FullNode
from golem.model import Payment, PaymentStatus
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.paymentmonitor import PaymentMonitor


def wait_for(condition, timeout, step=0.1):
    for _ in xrange(int(timeout / step)):
        if condition():
            return True
        time.sleep(step)
    return False


class PaymentStatusTest(unittest.TestCase):
    def test_status(self):
        s = PaymentStatus(1)
        assert s == PaymentStatus.awaiting

    def test_status2(self):
        s = PaymentStatus.awaiting
        assert s == PaymentStatus.awaiting


class PaymentProcessorTest(TestWithDatabase):
    RESERVATION = PaymentProcessor.GAS_PRICE * PaymentProcessor.GAS_RESERVATION

    def setUp(self):
        TestWithDatabase.setUp(self)
        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        self.client = mock.MagicMock(spec=Client)
        self.client.send.side_effect = lambda tx: "0x" + tx.hash.encode('hex')
        # FIXME: PaymentProcessor should be started and stopped!
        self.pp = PaymentProcessor(self.client, self.privkey)

    def test_balance(self):
        expected_balance = random.randint(0, 2**128 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.balance()
        assert b == expected_balance
        b = self.pp.balance()
        assert b == expected_balance
        self.client.get_balance.assert_called_once_with(self.addr.encode('hex'))

    def test_balance_refresh(self):
        expected_balance = random.randint(0, 2**128 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.balance()
        assert b == expected_balance
        self.client.get_balance.assert_called_once_with(self.addr.encode('hex'))
        b = self.pp.balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_balance_refresh_increase(self):
        expected_balance = random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.balance(refresh=True)
        assert b == expected_balance
        self.client.get_balance.assert_called_once_with(self.addr.encode('hex'))

        expected_balance += random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        assert self.pp.balance() == b
        b = self.pp.balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_balance_refresh_decrease(self):
        expected_balance = random.randint(0, 2**127 - 1)
        self.client.get_balance.return_value = expected_balance
        b = self.pp.balance(refresh=True)
        assert b == expected_balance
        self.client.get_balance.assert_called_once_with(self.addr.encode('hex'))

        expected_balance -= random.randint(0, expected_balance)
        assert expected_balance >= 0
        self.client.get_balance.return_value = expected_balance
        b = self.pp.balance(refresh=True)
        assert b == expected_balance
        assert self.client.get_balance.call_count == 2

    def test_available_balance_zero(self):
        self.client.get_balance.return_value = 0
        assert self.pp.available_balance() == 0

    def test_available_balance_egde(self):
        self.client.get_balance.return_value = self.RESERVATION
        assert self.pp.available_balance() == 0

    def test_available_balance_small(self):
        small_balance = random.randint(0, self.RESERVATION)
        self.client.get_balance.return_value = small_balance
        assert self.pp.available_balance() == 0

    def test_available_balance_one(self):
        self.client.get_balance.return_value = self.RESERVATION + 1
        assert self.pp.available_balance() == 1

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
        self.client.get_balance.assert_called_once_with(self.addr.encode('hex'))

        assert p1.status is PaymentStatus.awaiting
        assert p2.status is PaymentStatus.awaiting

    def test_faucet(self):
        self.client.get_balance.return_value = 0
        tx_nonce = random.randint(0, 999)
        self.client.get_transaction_count.return_value = tx_nonce
        PaymentProcessor(self.client, self.privkey, faucet=True)
        assert self.client.send.call_count == 1
        tx = self.client.send.call_args[0][0]
        assert tx.nonce == tx_nonce
        assert tx.value == 100 * 10**18


class EthereumMiningNodeFixture(TestDirFixture):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        super(EthereumMiningNodeFixture, self).setUp()
        miner_dir = path.join(self.path, "miner")
        node_dir = path.join(self.path, "node")
        self.miner = FullNode(datadir=miner_dir)
        enode = "enode://" + self.miner.proc.pubkey.encode('hex') + "@127.0.0.1:" + str(self.miner.proc.port)

        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        Client._kill_node()  # Kill the node to use random datadir
        self.client = Client(datadir=node_dir, nodes=[enode])
        assert wait_for(lambda: self.client.get_peer_count() > 0, 60), "Cannot connect to miner"
        self.proc = PaymentProcessor(self.client, self.privkey)

        self.bank_addr = Faucet.deploy_contract(self.client, BankOfDeposit.INIT_HEX.decode('hex'))
        assert self.bank_addr == PaymentProcessor.BANK_ADDR

    def tearDown(self):
        self.miner.proc.stop()  # Kill the miner to allow temp files removal.
        Client._kill_node()     # Kill the node to allow temp files removal.
        super(EthereumMiningNodeFixture, self).tearDown()


class PaymentProcessorFullTest(EthereumMiningNodeFixture, TestWithDatabase):
    def test_setup(self):
        pass

    def test_balance1(self):
        assert self.proc.available_balance() is 0
        value = 12 * 10**18
        Faucet.gimme_money(self.client, self.addr, value)
        assert self.proc.available_balance() is 0
        # 30 min to allow DAG generation
        assert wait_for(lambda: self.proc.available_balance(refresh=True) > 0,
                        30 * 60 * 10), "No income from faucet"
        b = self.proc.available_balance()
        assert b < 12 * 10**18
        assert b > 10 * 10**18

        a1 = urandom(20)
        a2 = urandom(20)
        p1 = Payment.create(subtask="p1", payee=a1, value=1 * 10**15)
        p2 = Payment.create(subtask="p2", payee=a2, value=2 * 10**15)

        assert self.proc.add(p1)
        assert self.proc.add(p2)

        self.proc.sendout()

        test1 = Payment.get(Payment.subtask == "p1")
        test2 = Payment.get(Payment.subtask == "p2")
        assert test1.status == PaymentStatus.sent
        assert test2.status == PaymentStatus.sent

        monitor = PaymentMonitor(self.client, a1)
        wait_for(lambda: monitor.get_incoming_payments(), 60)
        incoming = monitor.get_incoming_payments()
        assert incoming
        p = incoming[0]
        assert p.payer == self.addr
        assert p.value == 1 * 10**15

    def test_payment_aggregation(self):
        a1 = urandom(20)
        a2 = urandom(20)
        a3 = urandom(20)

        Faucet.gimme_money(self.client, self.addr, 100 * 10**18)
        assert wait_for(lambda: self.proc.available_balance(refresh=True) > 0,
                        30 * 60 * 10), "No income from faucet"

        assert self.proc.add(Payment.create(subtask="p1", payee=a1, value=1))
        assert self.proc.add(Payment.create(subtask="p2", payee=a2, value=1))
        assert self.proc.add(Payment.create(subtask="p3", payee=a2, value=1))
        assert self.proc.add(Payment.create(subtask="p4", payee=a3, value=1))
        assert self.proc.add(Payment.create(subtask="p5", payee=a3, value=1))
        assert self.proc.add(Payment.create(subtask="p6", payee=a3, value=1))

        self.proc.sendout()

        monitor = PaymentMonitor(self.client, a3)
        wait_for(lambda: monitor.get_incoming_payments(), 60)
        incoming = monitor.get_incoming_payments()
        assert incoming
        p = incoming[0]
        assert p.payer == self.addr
        assert p.value == 3
