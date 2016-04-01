import logging
import time
import unittest
from os import path, urandom

from ethereum.keys import privtoaddr

from golem.ethereum.contracts import BankOfDeposit
from golem.ethereum import Client
from golem.ethereum.node import Faucet, FullNode
from golem.tools.testdirfixture import TestDirFixture
from golem.transactions.ethereum.paymentprocessor import (
    Status, OutgoingPayment, PaymentProcessor
)
from golem.transactions.ethereum.paymentmonitor import PaymentMonitor


def wait_for(condition, timeout, step=0.1):
    for _ in xrange(int(timeout / step)):
        if condition():
            return True
        time.sleep(step)
    return False


class PaymentStatusTest(unittest.TestCase):
    def test_status(self):
        s = Status(1)
        assert s == Status.init

    def test_status2(self):
        s = Status.init
        assert s == Status.init


class EthereumNodeFixture(TestDirFixture):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        super(EthereumNodeFixture, self).setUp()
        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        # FIXME: Rename "client" to "node" or "eth_node"
        Client._kill_node()  # Kill the node to use random datadir
        self.client = Client(datadir=self.path)
        self.proc = PaymentProcessor(self.client, self.privkey)

    def tearDown(self):
        Client._kill_node()  # Kill the node to allow temp files removal
        super(EthereumNodeFixture, self).tearDown()


class PaymentProcessorTest(EthereumNodeFixture):
    def test_balance0(self):
        b = self.proc.available_balance()
        assert b == 0
        b = self.proc.available_balance()
        assert b == 0

    def test_balance1(self):
        assert self.proc.available_balance() is 0
        value = 11 * 10**17
        Faucet.gimme_money(self.client, self.addr, value)
        assert self.proc.available_balance() is 0
        self.proc.available_balance(refresh=True) is 0

    def test_add_failure(self):
        a1 = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'.decode('hex')
        a2 = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'.decode('hex')
        p1 = OutgoingPayment(a1, 1)
        p2 = OutgoingPayment(a2, 2)

        assert p1.status is Status.init
        assert p2.status is Status.init

        assert self.proc.add(p1) is False
        assert self.proc.add(p2) is False

        assert p1.status is Status.init
        assert p2.status is Status.init

    def test_double_kill(self):
        Client._kill_node()
        Client._kill_node()


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
        assert wait_for(lambda: self.client.get_peer_count() > 0, 20), "Cannot connect to miner"
        self.proc = PaymentProcessor(self.client, self.privkey)

        self.bank_addr = Faucet.deploy_contract(self.client, BankOfDeposit.INIT_HEX.decode('hex'))
        assert self.bank_addr == PaymentProcessor.BANK_ADDR

    def tearDown(self):
        self.miner.proc.stop()  # Kill the miner to allow temp files removal.
        Client._kill_node()     # Kill the node to allow temp files removal.
        super(EthereumMiningNodeFixture, self).tearDown()


class PaymentProcessorFullTest(EthereumMiningNodeFixture):
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

        a1 = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'.decode('hex')
        a2 = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'.decode('hex')
        p1 = OutgoingPayment(a1, 1 * 10**15)
        p2 = OutgoingPayment(a2, 2 * 10**15)

        assert self.proc.add(p1)
        assert self.proc.add(p2)

        self.proc.sendout()

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

        assert self.proc.add(OutgoingPayment(a1, 1))
        assert self.proc.add(OutgoingPayment(a2, 1))
        assert self.proc.add(OutgoingPayment(a2, 1))
        assert self.proc.add(OutgoingPayment(a3, 1))
        assert self.proc.add(OutgoingPayment(a3, 1))
        assert self.proc.add(OutgoingPayment(a3, 1))

        self.proc.sendout()

        monitor = PaymentMonitor(self.client, a3)
        wait_for(lambda: monitor.get_incoming_payments(), 60)
        incoming = monitor.get_incoming_payments()
        assert incoming
        p = incoming[0]
        assert p.payer == self.addr
        assert p.value == 3
