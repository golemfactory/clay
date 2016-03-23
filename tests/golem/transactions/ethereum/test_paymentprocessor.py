import unittest

from golem.ethereum import Client
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
    def test_balance(self):
        privkey = 32 * 'x'
        proc = PaymentProcessor(Client(), privkey)
        b = proc._PaymentProcessor__available_balance()
        assert b == 0
        b = proc._PaymentProcessor__available_balance()
        assert b == 0

    def test_add_failure(self):
        privkey = 32 * 'x'
        p1 = OutgoingPayment("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 1)
        p2 = OutgoingPayment("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab", 2)

        assert p1.status is Status.init
        assert p2.status is Status.init

        client = Client()
        proc = PaymentProcessor(client, privkey)
        assert proc.add(p1) is False
        assert proc.add(p2) is False

        assert p1.status is Status.init
        assert p2.status is Status.init
