import os
import random
import unittest
import uuid

import mock

from golem import model
from golem import testutils
from golem.ethereum import paymentprocessor
from golem.utils import encode_hex


def mock_token():
    token = mock.Mock()
    token.GAS_PRICE = 0
    token.GAS_PER_PAYMENT = 0
    token.GAS_BATCH_PAYMENT_BASE = 0
    return token


class TestPaymentProcessor(unittest.TestCase):
    def setUp(self):
        privkey = (b'!\xcd!^\xfe#\x82-#!Z]b\xb4\x8ce[\n\xfbN\x18V\x8c\x1dA'
                   b'\xea\x8c\xe8ZO\xc9\xdb')
        with mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.load_from_db"):  # noqa
            self.payment_processor = paymentprocessor.PaymentProcessor(
                client=mock.MagicMock(),
                privkey=privkey,
                token=mock_token()
            )

    def test_eth_address(self):
        # Test with zpad
        expected = ('0x000000000000000000000000e1ad9e38fc4bf20e5'
                    'd4847e00e8a05170c87913f')
        self.assertEqual(expected, self.payment_processor.eth_address())

        # Test without zpad
        expected = '0xe1ad9e38fc4bf20e5d4847e00e8a05170c87913f'
        result = self.payment_processor.eth_address(zpad=False)
        self.assertEqual(expected, result)


class TestPaymentProcessorWithDB(testutils.DatabaseFixture):
    def setUp(self):
        super(TestPaymentProcessorWithDB, self).setUp()
        random.seed()
        privkey = os.urandom(32)
        client = mock.MagicMock()
        self.payment_processor = paymentprocessor.PaymentProcessor(
            client=client,
            privkey=privkey,
            token=mock_token()
        )

    @mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.eth_balance", return_value=2**100)  # noqa
    @mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.gnt_balance", return_value=2**11)  # noqa
    def test_load_from_db(self, gnt_balance_mock, eth_balance_mock):
        self.assertEqual([], self.payment_processor._awaiting)

        subtask_id = str(uuid.uuid4())
        value = random.randint(1, 2**5)
        payee = encode_hex(os.urandom(32))
        payment = model.Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value
        )
        self.payment_processor.add(payment)

        self.payment_processor._awaiting = []
        self.payment_processor.load_from_db()
        expected = [payment]
        self.assertEqual(expected, self.payment_processor._awaiting)

        # Sent payments
        self.assertEqual({}, self.payment_processor._inprogress)
        tx_hash = os.urandom(32)
        sent_payment = model.Payment.create(
            subtask='sent' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details=model.PaymentDetails(tx=encode_hex(tx_hash)),
            status=model.PaymentStatus.sent
        )
        sent_payment2 = model.Payment.create(
            subtask='sent2' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details=model.PaymentDetails(tx=encode_hex(tx_hash)),
            status=model.PaymentStatus.sent
        )
        self.payment_processor.load_from_db()
        expected = {
            tx_hash: [sent_payment, sent_payment2],
        }
        self.assertEqual(expected, self.payment_processor._inprogress)
