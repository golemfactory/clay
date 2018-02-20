import random
import time

from golem.model import db, Income
from golem.testutils import PEP8MixIn
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.incomeskeeper import IncomesKeeper
from golem.utils import pubkeytoaddr

# SQLITE3_MAX_INT = 2 ** 31 - 1 # old one

# bigint - 8 Bytes
# -2^63 (-9,223,372,036,854,775,808) to
#  2^63-1 (9,223,372,036,854,775,807)

MAX_INT = 2 ** 63
# this proves that Golem's HexIntegerField wrapper does not
# overflows in contrast to standard SQL implementation


def generate_some_id(prefix='test'):
    return "%s-%d-%d" % (prefix, time.time() * 1000, random.random() * 1000)


class TestIncomesKeeper(TestWithDatabase, PEP8MixIn):
    PEP8_FILES = [
        'golem/transactions/incomeskeeper.py',
    ]

    def setUp(self):
        super(TestIncomesKeeper, self).setUp()
        random.seed()
        self.incomes_keeper = IncomesKeeper()

    def _test_expect_income(self, sender_node_id, subtask_id, value):
        self.incomes_keeper.expect(
            sender_node_id=sender_node_id,
            subtask_id=subtask_id,
            value=value
        )
        with db.atomic():
            expected_income = Income.get(
                sender_node=sender_node_id,
                subtask=subtask_id,
            )
        assert expected_income.value == value
        assert expected_income.accepted_ts is None
        assert expected_income.transaction is None

    def test_received_batch_transfer_closure_time(self):
        sender_node_id = '0x' + 64 * 'a'
        subtask_id1 = 'sample_subtask_id1'
        value1 = MAX_INT + 10
        accepted_ts1 = 1337
        subtask_id2 = 'sample_subtask_id2'
        value2 = MAX_INT + 100
        accepted_ts2 = 2137

        assert Income.select().count() == 0
        self._test_expect_income(
            sender_node_id=sender_node_id,
            subtask_id=subtask_id1,
            value=value1,
        )
        self._test_expect_income(
            sender_node_id=sender_node_id,
            subtask_id=subtask_id2,
            value=value2,
        )
        assert Income.select().count() == 2

        transaction_id = '0x' + 64 * '1'
        transaction_id1 = '0x' + 64 * 'b'
        transaction_id2 = '0x' + 64 * 'c'

        # incomes not accepted, so this in no op
        self.incomes_keeper.received_batch_transfer(
            transaction_id,
            pubkeytoaddr(sender_node_id),
            value1,
            accepted_ts2,
        )
        income1 = Income.get(sender_node=sender_node_id, subtask=subtask_id1)
        assert income1.transaction is None
        income2 = Income.get(sender_node=sender_node_id, subtask=subtask_id2)
        assert income2.transaction is None

        # now we accept both
        self.incomes_keeper.update_awaiting(subtask_id1, accepted_ts1)
        self.incomes_keeper.update_awaiting(subtask_id2, accepted_ts2)
        self.incomes_keeper.received_batch_transfer(
            transaction_id1,
            pubkeytoaddr(sender_node_id),
            value1,
            accepted_ts1,
        )
        income1 = Income.get(sender_node=sender_node_id, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node_id, subtask=subtask_id2)
        assert income2.transaction is None
        self.incomes_keeper.received_batch_transfer(
            transaction_id2,
            pubkeytoaddr(sender_node_id),
            value2,
            accepted_ts2,
        )
        income1 = Income.get(sender_node=sender_node_id, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node_id, subtask=subtask_id2)
        assert transaction_id2[2:] == income2.transaction

    def test_received_batch_transfer_two_senders(self):
        sender_node_id1 = '0x' + 64 * 'a'
        sender_node_id2 = '0x' + 64 * 'b'
        subtask_id1 = 'sample_subtask_id1'
        subtask_id2 = 'sample_subtask_id2'
        value1 = MAX_INT + 10
        value2 = MAX_INT + 100

        assert Income.select().count() == 0
        self._test_expect_income(
            sender_node_id=sender_node_id1,
            subtask_id=subtask_id1,
            value=value1,
        )
        self._test_expect_income(
            sender_node_id=sender_node_id2,
            subtask_id=subtask_id2,
            value=value2,
        )
        assert Income.select().count() == 2

        transaction_id1 = '0x' + 64 * 'b'
        transaction_id2 = '0x' + 64 * 'd'
        closure_time1 = 1337
        closure_time2 = 2137

        self.incomes_keeper.update_awaiting(subtask_id1, closure_time1)
        self.incomes_keeper.received_batch_transfer(
            transaction_id1,
            pubkeytoaddr(sender_node_id1),
            value1,
            closure_time1,
        )
        income1 = Income.get(sender_node=sender_node_id1, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node_id2, subtask=subtask_id2)
        assert income2.transaction is None

        self.incomes_keeper.update_awaiting(subtask_id2, closure_time2)
        self.incomes_keeper.received_batch_transfer(
            transaction_id2,
            pubkeytoaddr(sender_node_id2),
            value2,
            closure_time2,
        )
        income1 = Income.get(sender_node=sender_node_id1, subtask=subtask_id1)
        assert transaction_id1[2:] == income1.transaction
        income2 = Income.get(sender_node=sender_node_id2, subtask=subtask_id2)
        assert transaction_id2[2:] == income2.transaction
