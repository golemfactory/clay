from eth_utils import encode_hex
from os import urandom

from golem.model import PaymentStatus
from golem.ethereum.paymentskeeper import PaymentsDatabase, PaymentsKeeper
from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.ci import ci_skip
from tests.factories.model import Payment as PaymentFactory


@ci_skip  # Windows gives random failures #1738
class TestPaymentsKeeper(TestWithDatabase):
    def test_init(self):
        pk = PaymentsKeeper()
        self.assertIsInstance(pk, PaymentsKeeper)

    def test_database(self):
        pk = PaymentsKeeper()
        addr = urandom(20)
        addr2 = urandom(20)
        pk.finished_subtasks("xxyyzz", addr2, 2023)
        pk.finished_subtasks("aabbcc", addr2, 2023)
        pk.finished_subtasks("xxxyyy", addr2, 2023)
        pk.finished_subtasks("zzzzzz", addr, 10)
        pk.finished_subtasks("xxxxxx", addr, 10)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 5)
        self.assertEqual(all_payments[0]["subtask"], "xxxxxx")
        self.assertEqual(all_payments[0]["payee"], encode_hex(addr))
        self.assertEqual(all_payments[0]["value"], str(10))
        self.assertEqual(all_payments[0]["status"], PaymentStatus.awaiting.name)
        self.assertEqual(all_payments[1]["subtask"], "zzzzzz")
        self.assertEqual(all_payments[1]["payee"], encode_hex(addr))
        self.assertEqual(all_payments[1]["value"], str(10))
        self.assertEqual(all_payments[1]["status"], PaymentStatus.awaiting.name)
        self.assertEqual(all_payments[2]["subtask"], "xxxyyy")
        self.assertEqual(all_payments[2]["payee"], encode_hex(addr2))
        self.assertEqual(all_payments[2]["value"], str(2023))
        self.assertEqual(all_payments[2]["status"], PaymentStatus.awaiting.name)
        pk.finished_subtasks("whaooa!", addr, 10)
        all_payments = pk.get_list_of_all_payments()
        self.assertEqual(len(all_payments), 6)
        assert pk.get_payment("xxyyzz") == 2023
        assert pk.get_payment("not existing") == 0


class TestGetTotalPaymentForSubtasks(TestWithDatabase):

    def setUp(self):
        super().setUp()
        self.pd = PaymentsDatabase()

    @staticmethod
    def _create_payment(**kwargs):
        payment = PaymentFactory(**kwargs)
        payment.save(force_insert=True)
        return payment

    def test_no_payments(self):
        result = self.pd.get_total_payment_for_subtasks(('id1',))
        self.assertEqual(result, (None, None))

    def test_wrong_id(self):
        self._create_payment(subtask='id1', status=PaymentStatus.confirmed)
        result = self.pd.get_total_payment_for_subtasks(('id2',))
        self.assertEqual(result, (None, None))

    def test_awaiting_status(self):
        self._create_payment(subtask='id1', status=PaymentStatus.awaiting)
        result = self.pd.get_total_payment_for_subtasks(('id1',))
        self.assertEqual(result, (None, None))

    def test_sent_status(self):
        payment = self._create_payment(
            subtask='id1',
            status=PaymentStatus.sent)
        result = self.pd.get_total_payment_for_subtasks(('id1',))
        self.assertEqual(
            result,
            (payment.value, payment.details.fee))  # pylint: disable=no-member

    def test_confirmed_status(self):
        payment = self._create_payment(
            subtask='id1',
            status=PaymentStatus.confirmed)
        result = self.pd.get_total_payment_for_subtasks(('id1',))
        self.assertEqual(
            result,
            (payment.value, payment.details.fee))  # pylint: disable=no-member

    def test_sent_and_confirmed_status(self):
        p1 = self._create_payment(
            subtask='id1',
            status=PaymentStatus.sent)
        p2 = self._create_payment(
            subtask='id2',
            status=PaymentStatus.confirmed)
        result = self.pd.get_total_payment_for_subtasks(('id1', 'id2'))
        exp_value = p1.value + p2.value
        exp_fee = p1.details.fee + p2.details.fee  # pylint: disable=no-member
        self.assertEqual(result, (exp_value, exp_fee))

    def test_awaiting_and_confirmed_status(self):
        self._create_payment(
            subtask='id1',
            status=PaymentStatus.awaiting)
        self._create_payment(
            subtask='id2',
            status=PaymentStatus.confirmed)
        result = self.pd.get_total_payment_for_subtasks(('id1', 'id2'))
        self.assertEqual(result, (None, None))

    def test_ignored_subtasks(self):
        p1 = self._create_payment(
            subtask='id1',
            status=PaymentStatus.confirmed)
        p2 = self._create_payment(
            subtask='id2',
            status=PaymentStatus.confirmed)
        self._create_payment(
            subtask='id3',
            status=PaymentStatus.confirmed)
        result = self.pd.get_total_payment_for_subtasks(('id1', 'id2'))
        exp_value = p1.value + p2.value
        exp_fee = p1.details.fee + p2.details.fee  # pylint: disable=no-member
        self.assertEqual(result, (exp_value, exp_fee))
