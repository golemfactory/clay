import unittest
from os import urandom

from ethereum.keys import privtoaddr

from golem.ethereum import Client
from golem.ethereum.node import Faucet
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


class PaymentProcessorTest(unittest.TestCase):
    def setUp(self):
        self.privkey = urandom(32)
        self.addr = privtoaddr(self.privkey)
        # FIXME: Rename "client" to "node" or "eth_node"
        self.client = Client()
        self.proc = PaymentProcessor(self.client, self.privkey)

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
        b = self.proc.available_balance(refresh=True)
        # assert b > 1 * 10**18  FIXME: mining needed

    def test_add_failure(self):
        p1 = OutgoingPayment("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 1)
        p2 = OutgoingPayment("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab", 2)

        assert p1.status is Status.init
        assert p2.status is Status.init

        assert self.proc.add(p1) is False
        assert self.proc.add(p2) is False

        assert p1.status is Status.init
        assert p2.status is Status.init
