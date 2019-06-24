from golem_messages.factories.helpers import (
    random_eth_address,
)

from golem import model
from golem.ethereum.paymentskeeper import PaymentsDatabase
from golem.ethereum.paymentskeeper import PaymentsKeeper
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
        payment.wallet_operation.save(force_insert=True)
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


class TestPaymentsKeeper(TestWithDatabase):
    def setUp(self):
        super().setUp()
        self.payments_keeper = PaymentsKeeper()

    def test_sent_transfer(self):
        self.payments_keeper.sent_transfer(
            tx_hash=f"0x{'0'*64}",
            sender_address=random_eth_address(),
            recipient_address=random_eth_address(),
            amount=1,
            currency=model.WalletOperation.CURRENCY.GNT,
        )
        self.assertEqual(
            model.WalletOperation.select().count(),
            1,
        )
