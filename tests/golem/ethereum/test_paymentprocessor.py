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

    @mock.patch("golem.ethereum.paymentprocessor.PaymentProcessor.gnt_balance", return_value=2**11)  # noqa
    def test_load_from_db(self, balance_mock):
        self.assertEquals([], self.payment_processor._awaiting)

        subtask_id = str(uuid.uuid4())
        value = random.randint(1, 2**10)
        payee = os.urandom(32)
        payment = model.Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value
        )
        self.assertTrue(self.payment_processor.add(payment))

        # Shouldn't add duplicate
        self.assertFalse(self.payment_processor.add(payment))
        self.assertEquals([payment], self.payment_processor._awaiting)

        self.payment_processor._awaiting = []
        self.payment_processor.load_from_db()
        expected = [payment]
        self.assertEquals(expected, self.payment_processor._awaiting)
