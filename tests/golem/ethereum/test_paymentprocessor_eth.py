import mock
import os
import random
import unittest
import uuid

from golem import model
from golem import testutils
from golem.ethereum import paymentprocessor


class TestPaymentProcessor(unittest.TestCase):
    def setUp(self):
        privkey = ('!\xcd!^\xfe#\x82-#!Z]b\xb4\x8ce[\n\xfbN\x18V\x8c\x1dA'
                   '\xea\x8c\xe8ZO\xc9\xdb')
        with mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.load_from_db"):  # noqa
            self.payment_processor = paymentprocessor.PaymentProcessor(
                client=mock.MagicMock(),
                privkey=privkey
            )

    def test_eth_address(self):
        # Test with zpad
        expected = ('0x000000000000000000000000'
                    'e1ad9e38fc4bf20e5d4847e00e8a05170c87913f')
        self.assertEquals(expected, self.payment_processor.eth_address())

        # Test without zpad
        expected = '0xe1ad9e38fc4bf20e5d4847e00e8a05170c87913f'
        result = self.payment_processor.eth_address(zpad=False)
        self.assertEquals(expected, result)


class TestPaymentProcessorWithDB(testutils.DatabaseFixture):
    def setUp(self):
        super(TestPaymentProcessorWithDB, self).setUp()
        random.seed()
        privkey = os.urandom(32)
        client = mock.MagicMock()
        self.payment_processor = paymentprocessor.PaymentProcessor(
            client=client,
            privkey=privkey
        )

    @mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.eth_balance", return_value=2**100)  # noqa
    @mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.gnt_balance", return_value=2**11)  # noqa
    def test_load_from_db(self, gnt_balance_mock, eth_balance_mock):
        self.assertEquals([], self.payment_processor._awaiting)

        subtask_id = str(uuid.uuid4())
        value = random.randint(1, 2**5)
        payee = os.urandom(32).encode('hex')
        payment = model.Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value
        )
        self.assertTrue(self.payment_processor.add(payment))

        self.payment_processor._awaiting = []
        self.payment_processor.load_from_db()
        expected = [payment]
        self.assertEquals(expected, self.payment_processor._awaiting)

        # Sent payments
        self.assertEquals({}, self.payment_processor._inprogress)
        tx_hash = os.urandom(32)
        sent_payment = model.Payment.create(
            subtask='sent' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details={'tx': tx_hash.encode('hex')},
            status=model.PaymentStatus.sent
        )
        sent_payment2 = model.Payment.create(
            subtask='sent2' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details={'tx': tx_hash.encode('hex')},
            status=model.PaymentStatus.sent
        )
        self.payment_processor.load_from_db()
        expected = {
            tx_hash: [sent_payment, sent_payment2],
        }
        self.assertEquals(expected, self.payment_processor._inprogress)
