import os
import random
import uuid

import mock

from golem import model
from golem import testutils
from golem.ethereum import paymentprocessor
from golem.utils import encode_hex


def mock_sci():
    sci = mock.Mock()
    sci.GAS_PRICE = 0
    sci.GAS_PER_PAYMENT = 0
    sci.GAS_BATCH_PAYMENT_BASE = 0
    return sci


class TestPaymentProcessorWithDB(testutils.DatabaseFixture):
    def setUp(self):
        super(TestPaymentProcessorWithDB, self).setUp()
        random.seed()
        self.payment_processor = paymentprocessor.PaymentProcessor(
            sci=mock_sci()
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
        tx_hash = '0x' + encode_hex(os.urandom(32))
        sent_payment = model.Payment.create(
            subtask='sent' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details=model.PaymentDetails(tx=tx_hash[2:]),
            status=model.PaymentStatus.sent
        )
        sent_payment2 = model.Payment.create(
            subtask='sent2' + str(uuid.uuid4()),
            payee=payee,
            value=value,
            details=model.PaymentDetails(tx=tx_hash[2:]),
            status=model.PaymentStatus.sent
        )
        self.payment_processor.load_from_db()
        expected = {
            tx_hash: [sent_payment, sent_payment2],
        }
        self.assertEqual(expected, self.payment_processor._inprogress)
