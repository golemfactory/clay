from datetime import datetime, timedelta
from random import Random
import time
import unittest.mock as mock

from freezegun import freeze_time

from golem.core.variables import PAYMENT_DEADLINE
from golem.ethereum.incomeskeeper import IncomesKeeper
from golem.model import db, Income
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
            subtask_id=subtask_id,
            payer_address=payer_addr,
            value=value,
            accepted_ts=accepted_ts,
        )
        with db.atomic():
            expected_income = Income.get(
                sender_node=sender_node,
                subtask=subtask_id,
            )
        assert expected_income.value == value
        assert expected_income.transaction is None

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
        batch_mock.assert_called_once_with(**kwargs)

    def test_received_batch_transfer_closure_time(self):
        sender_node = 64 * 'a'
        payer_address = '0x' + 40 * '9'
        subtask_id1 = 'sample_subtask_id1'
        value1 = MAX_INT + 10
        accepted_ts1 = 1337
        subtask_id2 = 'sample_subtask_id2'
        value2 = MAX_INT + 100
        accepted_ts2 = 2137

        assert Income.select().count() == 0
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
        assert Income.select().count() == 2

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
        income1 = Income.get(sender_node=sender_node, subtask=subtask_id1)
        assert income1.transaction is None
        income2 = Income.get(sender_node=sender_node, subtask=subtask_id2)
        assert income2.transaction is None

        self.incomes_keeper.received_batch_transfer(
            transaction_id1,
            payer_address,
            value1,
            accepted_ts1,
        )
        income1 = Income.get(sender_node=sender_node, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node, subtask=subtask_id2)
        assert income2.transaction is None

        self.incomes_keeper.received_batch_transfer(
            transaction_id2,
            payer_address,
            value2,
            accepted_ts2,
        )
        income1 = Income.get(sender_node=sender_node, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node, subtask=subtask_id2)
        assert transaction_id2[2:] == income2.transaction

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

        assert Income.select().count() == 0
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
        assert Income.select().count() == 2

        transaction_id1 = '0x' + 64 * 'b'
        transaction_id2 = '0x' + 64 * 'd'

        self.incomes_keeper.received_batch_transfer(
            transaction_id1,
            payer_address1,
            value1,
            closure_time1,
        )
        income1 = Income.get(sender_node=sender_node1, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node2, subtask=subtask_id2)
        assert income2.transaction is None

        self.incomes_keeper.received_batch_transfer(
            transaction_id2,
            payer_address2,
            value2,
            closure_time2,
        )
        income1 = Income.get(sender_node=sender_node1, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node2, subtask=subtask_id2)
        assert transaction_id2[2:] == income2.transaction

    @staticmethod
    def _create_income(**kwargs):
        income = model_factories.Income(**kwargs)
        income.save(force_insert=True)
        return income

    def test_expect_income_accepted_ts(self):
        sender_node = 64 * 'a'
        payer_address = '0x' + 40 * '1'
        subtask_id = 'sample_subtask_id1'
        value = 123
        accepted_ts = 1337
        income = self._create_income(
            sender_node=sender_node,
            subtask=subtask_id,
            payer_address=payer_address,
            value=value,
        )
        assert income.accepted_ts is None
        self.incomes_keeper.expect(
            sender_node,
            subtask_id,
            payer_address,
            value,
            accepted_ts,
        )
        income = Income.get(sender_node=sender_node, subtask=subtask_id)
        assert income.accepted_ts == accepted_ts
        self.incomes_keeper.expect(
            sender_node,
            subtask_id,
            payer_address,
            value,
            accepted_ts + 1,
        )
        income = Income.get(sender_node=sender_node, subtask=subtask_id)
        assert income.accepted_ts == accepted_ts

    @freeze_time()
    def test_update_overdue_incomes_all_paid(self):
        income1 = self._create_income(
            accepted_ts=int(time.time()),
            transaction='transaction')
        income2 = self._create_income(
            created_date=datetime.now() - timedelta(seconds=2*PAYMENT_DEADLINE),
            accepted_ts=int(time.time()) - 2*PAYMENT_DEADLINE,
            transaction='transaction')
        self.incomes_keeper.update_overdue_incomes()
        self.assertFalse(income1.refresh().overdue)
        self.assertFalse(income2.refresh().overdue)

    @freeze_time()
    def test_update_overdue_incomes_accepted_deadline_passed(self):
        overdue_income = self._create_income(
            created_date=datetime.now() - timedelta(seconds=2*PAYMENT_DEADLINE),
            accepted_ts=int(time.time()) - 2*PAYMENT_DEADLINE)
        self.incomes_keeper.update_overdue_incomes()
        self.assertTrue(overdue_income.refresh().overdue)

    @freeze_time()
    def test_update_overdue_incomes_old_but_recently_accepted(self):
        income = self._create_income(
            created_date=datetime.now() - timedelta(seconds=2*PAYMENT_DEADLINE),
            accepted_ts=int(time.time()))
        self.incomes_keeper.update_overdue_incomes()
        self.assertFalse(income.refresh().overdue)

    @freeze_time()
    def test_update_overdue_incomes_already_marked_as_overdue(self):
        income = self._create_income(
            created_date=datetime.now() - timedelta(seconds=2*PAYMENT_DEADLINE),
            accepted_ts=int(time.time()) - 2*PAYMENT_DEADLINE,
            overdue=True)
        self.incomes_keeper.update_overdue_incomes()
        self.assertTrue(income.refresh().overdue)
