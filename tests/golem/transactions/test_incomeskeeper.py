import datetime
import random
import time

from golem.model import db
from golem.model import ExpectedIncome
from golem.model import Income
from golem.network.p2p.node import Node
from golem.testutils import PEP8MixIn
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.incomeskeeper import IncomesKeeper

# SQLITE3_MAX_INT = 2 ** 31 - 1 # old one

# bigint - 8 Bytes
# -2^63 (-9,223,372,036,854,775,808) to
#  2^63-1 (9,223,372,036,854,775,807)

MAX_INT = 2 ** 63
# this proves that Golem's BigIntegerField wrapper does not
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
            p2p_node=Node(),
            value=value
        )
        with db.atomic():
            expected_income = ExpectedIncome.get(sender_node=sender_node_id,
                                                 subtask=subtask_id)
        self.assertEqual(expected_income.value, value)

    def test_received(self):
        sender_node_id = generate_some_id('sender_node_id')
        subtask_id = generate_some_id('subtask_id')
        value = random.randint(MAX_INT, MAX_INT + 10)

        self.assertEqual(ExpectedIncome.select().count(), 0)
        self._test_expect_income(sender_node_id=sender_node_id,
                                 subtask_id=subtask_id,
                                 value=value
                                 )
        self.assertEqual(ExpectedIncome.select().count(), 1)

        transaction_id = generate_some_id('transaction_id')
        income = self.incomes_keeper.received(
            sender_node_id=sender_node_id,
            subtask_id=subtask_id,
            transaction_id=transaction_id,
            value=value
        )

        self.assertEqual(ExpectedIncome.select().count(), 0)
        assert type(income) is Income
        self.assertIsNotNone(income)

        with db.atomic():
            income = Income.get(sender_node=sender_node_id, subtask=subtask_id)
        self.assertEqual(income.value, value)
        self.assertEqual(income.transaction, transaction_id)

        # try to duplicate key
        # same sender cannot pay for the same subtask twice
        new_transaction = generate_some_id('transaction_id2')
        new_value = random.randint(MAX_INT, MAX_INT + 10)
        income = self.incomes_keeper.received(
            sender_node_id=sender_node_id,
            subtask_id=subtask_id,
            transaction_id=new_transaction,
            value=new_value
        )
        self.assertIsNone(income)

    def test_run_once(self):
        sender_node_id = generate_some_id('sender_node_id')
        subtask_id = generate_some_id('subtask_id')
        value = random.randint(MAX_INT, MAX_INT + 10)
        transaction_id = generate_some_id('transaction_id')

        expected_income = self.incomes_keeper.expect(
            sender_node_id=sender_node_id,
            p2p_node=Node(),
            subtask_id=subtask_id,
            value=value
        )

        # expected payment written to DB
        self.assertEqual(ExpectedIncome.select().count(), 1)

        # Time is right but no matching payment received
        with db.atomic():
            expected_income.modified_date \
                = datetime.datetime.now() \
                - datetime.timedelta(hours=1)
            expected_income.save()

        self.incomes_keeper.run_once()
        self.assertEqual(ExpectedIncome.select().count(), 1)

        # Matching received but too early to check
        Income.create(
            sender_node=sender_node_id,
            subtask=subtask_id,
            transaction=transaction_id,
            value=value)

        with db.atomic():
            self.assertEqual(ExpectedIncome.select().count(), 1)
            expected_income.modified_date \
                = datetime.datetime.now() \
                + datetime.timedelta(hours=1)
            expected_income.save()

        self.incomes_keeper.run_once()
        self.assertEqual(ExpectedIncome.select().count(), 1)

        # Match
        with db.atomic():
            expected_income.modified_date = \
                datetime.datetime.now() \
                - datetime.timedelta(hours=1)
            expected_income.save()

        self.incomes_keeper.run_once()
        with db.atomic():
            self.assertEqual(ExpectedIncome.select().count(), 0)
