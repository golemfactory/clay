from random import Random
import time
import unittest.mock as mock
import uuid

from freezegun import freeze_time
from golem_messages.factories.helpers import (
    random_eth_address,
    random_eth_pub_key,
)

from golem import model
from golem.core.variables import PAYMENT_DEADLINE
from golem.ethereum.incomeskeeper import IncomesKeeper
from golem.tools.testwithdatabase import TestWithDatabase
from tests.factories import model as model_factories

# SQLITE3_MAX_INT = 2 ** 31 - 1 # old one

# bigint - 8 Bytes
# -2^63 (-9,223,372,036,854,775,808) to
#  2^63-1 (9,223,372,036,854,775,807)

MAX_INT = 2 ** 63
# this proves that Golem's HexIntegerField wrapper does not
# overflows in contrast to standard SQL implementation

random = Random()


def generate_some_id(prefix='test'):
    return "%s-%d-%d" % (prefix, time.time() * 1000, random.random() * 1000)


class TestIncomesKeeper(TestWithDatabase):
    def setUp(self):
        super(TestIncomesKeeper, self).setUp()
        random.seed(__name__)
        self.incomes_keeper = IncomesKeeper()

    def assertIncomeHash(self, sender_node, subtask_id, transaction_id):
        income = self._get_income(
            model.TaskPayment.node == sender_node,
            model.TaskPayment.subtask == subtask_id,
        )
        self.assertEqual(income.wallet_operation.tx_hash, transaction_id)

    # pylint:disable=too-many-arguments
    def _test_expect_income(
            self,
            sender_node,
            subtask_id,
            payer_addr,
            value,
            accepted_ts):
        self.incomes_keeper.expect(
            sender_node=sender_node,
            my_address=random_eth_address(),
            task_id=str(uuid.uuid4()),
            subtask_id=subtask_id,
            payer_address=payer_addr,
            value=value,
            accepted_ts=accepted_ts,
        )
        with model.db.atomic():
            expected_income = model.TaskPayment \
                .incomes() \
                .where(
                    model.TaskPayment.node == sender_node,
                    model.TaskPayment.subtask == subtask_id,
                ) \
                .get()
        self.assertEqual(expected_income.expected_amount, value)
        self.assertIsNone(expected_income.wallet_operation.tx_hash)

    @mock.patch("golem.ethereum.incomeskeeper.IncomesKeeper"
                ".received_batch_transfer")
    def test_received_forced_payment(self, batch_mock):
        kwargs = {
            'tx_hash': object(),
            'sender': object(),
            'amount': object(),
            'closure_time': object(),
        }
        self.incomes_keeper.received_forced_payment(
            **kwargs,
        )
        batch_mock.assert_called_once_with(
            **kwargs,
            charged_from_deposit=True,
        )

    def test_received_batch_transfer_closure_time(self):
        sender_node = 64 * 'a'
        payer_address = '0x' + 40 * '9'
        subtask_id1 = 'sample_subtask_id1'
        value1 = MAX_INT + 10
        accepted_ts1 = 1337
        subtask_id2 = 'sample_subtask_id2'
        value2 = MAX_INT + 100
        accepted_ts2 = 2137

        self.assertEqual(model.TaskPayment.select().count(), 0)
        self._test_expect_income(
            sender_node=sender_node,
            subtask_id=subtask_id1,
            payer_addr=payer_address,
            value=value1,
            accepted_ts=accepted_ts1,
        )
        self._test_expect_income(
            sender_node=sender_node,
            subtask_id=subtask_id2,
            payer_addr=payer_address,
            value=value2,
            accepted_ts=accepted_ts2,
        )
        self.assertEqual(model.TaskPayment.select().count(), 2)

        transaction_id = '0x' + 64 * '1'
        transaction_id1 = '0x' + 64 * 'b'
        transaction_id2 = '0x' + 64 * 'c'

        # old closure_time so this is no op
        self.incomes_keeper.received_batch_transfer(
            transaction_id,
            payer_address,
            value1,
            accepted_ts1 - 1,
        )
        self.assertIncomeHash(sender_node, subtask_id1, None)
        self.assertIncomeHash(sender_node, subtask_id2, None)

        self.incomes_keeper.received_batch_transfer(
            transaction_id1,
            payer_address,
            value1,
            accepted_ts1,
        )
        self.assertIncomeHash(sender_node, subtask_id1, transaction_id1)
        self.assertIncomeHash(sender_node, subtask_id2, None)

        self.incomes_keeper.received_batch_transfer(
            transaction_id2,
            payer_address,
            value2,
            accepted_ts2,
        )
        self.assertIncomeHash(sender_node, subtask_id1, transaction_id1)
        self.assertIncomeHash(sender_node, subtask_id2, transaction_id2)

    def test_received_batch_transfer_two_senders(self):
        sender_node1 = 64 * 'a'
        sender_node2 = 64 * 'b'
        payer_address1 = '0x' + 40 * '1'
        payer_address2 = '0x' + 40 * '2'
        subtask_id1 = 'sample_subtask_id1'
        subtask_id2 = 'sample_subtask_id2'
        value1 = MAX_INT + 10
        value2 = MAX_INT + 100
        closure_time1 = 1337
        closure_time2 = 2137

        self.assertEqual(model.TaskPayment.incomes().count(), 0)
        self._test_expect_income(
            sender_node=sender_node1,
            subtask_id=subtask_id1,
            payer_addr=payer_address1,
            value=value1,
            accepted_ts=closure_time1,
        )
        self._test_expect_income(
            sender_node=sender_node2,
            subtask_id=subtask_id2,
            payer_addr=payer_address2,
            value=value2,
            accepted_ts=closure_time2,
        )
        self.assertEqual(model.TaskPayment.incomes().count(), 2)

        transaction_id1 = '0x' + 64 * 'b'
        transaction_id2 = '0x' + 64 * 'd'

        self.incomes_keeper.received_batch_transfer(
            transaction_id1,
            payer_address1,
            value1,
            closure_time1,
        )
        self.assertIncomeHash(sender_node1, subtask_id1, transaction_id1)
        self.assertIncomeHash(sender_node2, subtask_id2, None)

        self.incomes_keeper.received_batch_transfer(
            transaction_id2,
            payer_address2,
            value2,
            closure_time2,
        )
        self.assertIncomeHash(sender_node1, subtask_id1, transaction_id1)
        self.assertIncomeHash(sender_node2, subtask_id2, transaction_id2)

    @staticmethod
    def _create_income(**kwargs):
        income = model_factories.TaskPayment(
            wallet_operation__operation_type=  # noqa
            model.WalletOperation.TYPE.task_payment,
            wallet_operation__direction=  # noqa
            model.WalletOperation.DIRECTION.incoming,
            **kwargs,
        )
        income.wallet_operation.save(force_insert=True)
        income.save(force_insert=True)
        return income

    @staticmethod
    def _get_income(*args):
        return model.TaskPayment \
            .incomes() \
            .where(*args) \
            .get()

    def test_expect_income_accepted_ts(self):
        sender_node = random_eth_pub_key()
        payer_address = random_eth_address()
        subtask_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        value = 123
        accepted_ts = 1337
        expect_kwargs = {
            'my_address': random_eth_address(),
            'sender_node': sender_node,
            'task_id': task_id,
            'subtask_id': subtask_id,
            'payer_address': payer_address,
            'value': value,
            'accepted_ts': accepted_ts,
        }
        income = self.incomes_keeper.expect(**expect_kwargs)
        self.assertEqual(income.accepted_ts, accepted_ts)
        db_income = self._get_income(
            model.TaskPayment.node == sender_node,
            model.TaskPayment.subtask == subtask_id,
        )
        self.assertEqual(db_income.accepted_ts, accepted_ts)
        expect_kwargs['accepted_ts'] += 1
        self.incomes_keeper.expect(**expect_kwargs)
        db_income = self._get_income(
            model.TaskPayment.node == sender_node,
            model.TaskPayment.subtask == subtask_id,
        )
        self.assertEqual(db_income.accepted_ts, accepted_ts)

    @freeze_time()
    def test_update_overdue_incomes_all_paid(self):
        tx_hash = f'0x{"0"*64}'
        income1 = self._create_income(
            accepted_ts=int(time.time()),
            wallet_operation__status=model.WalletOperation.STATUS.awaiting,
            wallet_operation__tx_hash=tx_hash)
        income2 = self._create_income(
            accepted_ts=int(time.time()) - 2*PAYMENT_DEADLINE,
            wallet_operation__status=model.WalletOperation.STATUS.awaiting,
            wallet_operation__tx_hash=tx_hash)
        self.incomes_keeper.update_overdue_incomes()
        self.assertNotEqual(
            income1.wallet_operation.refresh().status,
            model.WalletOperation.STATUS.overdue,
        )
        self.assertNotEqual(
            income2.wallet_operation.refresh().status,
            model.WalletOperation.STATUS.overdue,
        )

    @freeze_time()
    def test_update_overdue_incomes_accepted_deadline_passed(self):
        overdue_income = self._create_income(
            accepted_ts=int(time.time()) - 2*PAYMENT_DEADLINE,
            wallet_operation__status=model.WalletOperation.STATUS.awaiting,
        )
        self.incomes_keeper.update_overdue_incomes()
        self.assertEqual(
            overdue_income.wallet_operation.refresh().status,
            model.WalletOperation.STATUS.overdue,
        )

    @freeze_time()
    def test_update_overdue_incomes_already_marked_as_overdue(self):
        income = self._create_income(
            accepted_ts=int(time.time()) - 2*PAYMENT_DEADLINE,
            wallet_operation__status=model.WalletOperation.STATUS.overdue,
        )
        self.incomes_keeper.update_overdue_incomes()
        self.assertEqual(
            income.wallet_operation.refresh().status,
            model.WalletOperation.STATUS.overdue,
        )

    def test_received_transfer(self):
        self.incomes_keeper.received_transfer(
            tx_hash=f"0x{'0'*64}",
            sender_address=random_eth_address(),
            recipient_address=random_eth_address(),
            amount=1,
            currency=model.WalletOperation.CURRENCY.ETH,
        )
        self.assertEqual(
            model.WalletOperation.select().count(),
            1,
        )
