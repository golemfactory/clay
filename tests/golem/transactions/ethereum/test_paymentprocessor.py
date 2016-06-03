import mock
import random
import time
import unittest
from os import urandom

from ethereum.keys import privtoaddr

from golem.ethereum import Client
from golem.ethereum.node import Faucet
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.model import Payment, PaymentStatus
from golem.testutils import DatabaseFixture


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


class PaymentProcessorTest(DatabaseFixture):
    RESERVATION = PaymentProcessor.GAS_PRICE * PaymentProcessor.GAS_RESERVATION

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
        pp = PaymentProcessor(self.client, self.privkey, faucet=True)
        pp.get_ethers_from_faucet()
        assert self.client.send.call_count == 1
        tx = self.client.send.call_args[0][0]
        assert tx.nonce == self.nonce
        assert tx.value == 100 * 10**18

    def test_faucet_gimme_money(self):
        assert self.pp.balance() == 0
        value = 12 * 10**18
        Faucet.gimme_money(self.client, self.addr, value)

    def test_payment_aggregation(self):
        a1 = urandom(20)
        a2 = urandom(20)
        a3 = urandom(20)

        self.client.get_balance.return_value = 100 * 10**18

        assert self.pp.add(Payment.create(subtask="p1", payee=a1, value=1))
        assert self.pp.add(Payment.create(subtask="p2", payee=a2, value=1))
        assert self.pp.add(Payment.create(subtask="p3", payee=a2, value=1))
        assert self.pp.add(Payment.create(subtask="p4", payee=a3, value=1))
        assert self.pp.add(Payment.create(subtask="p5", payee=a3, value=1))
        assert self.pp.add(Payment.create(subtask="p6", payee=a3, value=1))

        self.pp.sendout()
        assert self.client.send.call_count == 1
        tx = self.client.send.call_args[0][0]
        assert tx.value == 6
        assert len(tx.data) == 4 + 2*32 + 3*32  # Id + array abi + bytes32[3]
