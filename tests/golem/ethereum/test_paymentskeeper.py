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


class TestPaymentsDatabase(TestWithDatabase):
    @staticmethod
    def _create_payment(**kwargs):
        payment = PaymentFactory(**kwargs)
        payment.save(force_insert=True)
        return payment

    @staticmethod
    def _get_ids(payments):
        return [p.subtask for p in payments]

    def test_subtasks_payments(self):
        pd = PaymentsDatabase()
        self._create_payment(subtask='id1')
        self._create_payment(subtask='id2')
        self._create_payment(subtask='id3')

        payments = pd.get_subtasks_payments(['id1'])
        assert self._get_ids(payments) == ['id1']

        payments = pd.get_subtasks_payments(['id4'])
        assert self._get_ids(payments) == []

        payments = pd.get_subtasks_payments(['id1', 'id3'])
        assert self._get_ids(payments) == ['id1', 'id3']

        payments = pd.get_subtasks_payments([])
        assert self._get_ids(payments) == []

        payments = pd.get_subtasks_payments(['id1', 'id4', 'id2'])
        assert self._get_ids(payments) == ['id1', 'id2']
