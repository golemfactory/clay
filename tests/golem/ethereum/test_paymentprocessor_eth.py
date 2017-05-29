import mock
import os
import random
import uuid

from golem import model
from golem import testutils
from golem.ethereum import paymentprocessor


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
