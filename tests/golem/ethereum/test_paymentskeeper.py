from golem import model
from golem.ethereum.paymentskeeper import PaymentsDatabase
from golem.tools.testwithdatabase import TestWithDatabase
from tests.factories.model import TaskPayment as TaskPaymentFactory


class TestPaymentsDatabase(TestWithDatabase):
    @staticmethod
    def _create_payment(**kwargs):
        payment = TaskPaymentFactory(
            wallet_operation__operation_type=  # noqa
            model.WalletOperation.TYPE.task_payment,
            wallet_operation__direction=  # noqa
            model.WalletOperation.DIRECTION.outgoing,
            **kwargs,
        )
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
