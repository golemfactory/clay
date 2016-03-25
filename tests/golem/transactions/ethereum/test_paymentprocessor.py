import time
import unittest
from os import path, urandom

from ethereum.keys import privtoaddr

from golem.ethereum import Client
from golem.ethereum.node import Faucet, FullNode
from golem.tools.testdirfixture import TestDirFixture
from golem.transactions.ethereum.paymentprocessor import (
    Status, OutgoingPayment, PaymentProcessor
)


class PaymentStatusTest(unittest.TestCase):
    def test_status(self):
        s = Status(1)
        assert s == Status.init

    def test_status2(self):
        s = Status.init
        assert s == Status.init


class EthereumNodeFixture(TestDirFixture):
    def setUp(self):
        super(EthereumNodeFixture, self).setUp()
        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        # FIXME: Rename "client" to "node" or "eth_node"
        Client._kill_node()  # Kill the node to use random datadir
        self.client = Client(datadir=self.path)
        self.proc = PaymentProcessor(self.client, self.privkey)


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
        p1 = OutgoingPayment("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 1)
        p2 = OutgoingPayment("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab", 2)

        assert p1.status is Status.init
        assert p2.status is Status.init

        assert self.proc.add(p1) is False
        assert self.proc.add(p2) is False

        assert p1.status is Status.init
        assert p2.status is Status.init


class EthereumMiningNodeFixture(TestDirFixture):
    def setUp(self):
        super(EthereumMiningNodeFixture, self).setUp()
        miner_dir = path.join(self.path, "miner")
        node_dir = path.join(self.path, "node")
        self.miner = FullNode(datadir=miner_dir)
        enode = "enode://" + self.miner.proc.pubkey.encode('hex') + "@127.0.0.1:" + str(self.miner.proc.port)

        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        Client._kill_node()  # Kill the node to use random datadir
        self.client = Client(datadir=node_dir, nodes=[enode])
        for _ in xrange(20):
            time.sleep(0.1)
            if self.client.get_peer_count() > 0:
                break
        else:
            assert False, "Cannot connect to miner."
        self.proc = PaymentProcessor(self.client, self.privkey)


class PaymentProcessorFullTest(EthereumMiningNodeFixture):
    def test_balance1(self):
        assert self.proc.available_balance() is 0
        value = 12 * 10**18
        Faucet.gimme_money(self.client, self.addr, value)
        assert self.proc.available_balance() is 0
        for _ in xrange(30 * 60 * 10):  # 30 min to allow DAG generation
            time.sleep(0.1)
            b = self.proc.available_balance(refresh=True)
            if b != 0:
                break
        else:
            assert False, "Faucet does not work"
        assert b < 12 * 10**18
        assert b > 10 * 10**18
