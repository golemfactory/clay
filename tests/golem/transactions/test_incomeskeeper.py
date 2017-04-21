import datetime
from golem.model import db
from golem.model import ExpectedIncome
from golem.model import Income
from golem.testutils import PEP8MixIn
from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.assertlogs import LogTestCase
from golem.transactions.incomeskeeper import IncomesKeeper
import random
import time

random.seed()

def generate_some_id(prefix='test'):
    return "%s-%d-%d" % (prefix, time.time()*1000, random.random() * 1000)

class TestIncomesKeeper(TestWithDatabase, PEP8MixIn):
    PEP8_FILES = [
        'golem/transactions/incomeskeeper.py',
    ]
    def setUp(self):
        super(TestIncomesKeeper, self).setUp()
        self.incomes_keeper = IncomesKeeper()

    def test_expect(self):
        sender_node_id = generate_some_id('sender_node_id')
        task_id = generate_some_id('task_id')
        subtask_id = generate_some_id('subtask_id')
        value = random.randint(1, 10**5)
        self.incomes_keeper.expect(sender_node_id, task_id, subtask_id, value)
        with db.atomic():
            expected_income = ExpectedIncome.get(sender_node=sender_node_id, task=task_id, subtask=subtask_id)
        self.assertEquals(expected_income.value, value)

    def test_received(self):
        sender_node_id = generate_some_id('sender_node_id')
        task_id = generate_some_id('task_id')
        subtask_id = generate_some_id('subtask_id')
        value = random.randint(1, 10**5)
        transaction_id = generate_some_id('transaction_id')

        income = self.incomes_keeper.received(sender_node_id, task_id, subtask_id, transaction_id, value)
        self.assertIsNotNone(income)

        with db.atomic():
            income = Income.get(sender_node=sender_node_id, task=task_id, subtask=subtask_id)
        self.assertEquals(income.value, value)
        self.assertEquals(income.transaction, transaction_id)

        new_transaction = generate_some_id('transaction_id2')
        new_value = random.randint(1, 10**5)
        income = self.incomes_keeper.received(sender_node_id, task_id, subtask_id, new_transaction, new_value)
        self.assertIsNone(income)

    def test_run_once(self):
        sender_node_id = generate_some_id('sender_node_id')
        task_id = generate_some_id('task_id')
        subtask_id = generate_some_id('subtask_id')
        value = random.randint(1, 10**5)
        transaction_id = generate_some_id('transaction_id')

        expected_income = self.incomes_keeper.expect(sender_node_id, task_id, subtask_id, value)
        with db.atomic():
            self.assertEquals(ExpectedIncome.select().count(), 1)
            expected_income.modified_date = datetime.datetime.now() - datetime.timedelta(hours=1)
            expected_income.save()

        self.incomes_keeper.run_once()
        with db.atomic():
            # No matching received
            self.assertEquals(ExpectedIncome.select().count(), 1)

            expected_income.modified_date = datetime.datetime.now() + datetime.timedelta(hours=1)
            expected_income.save()

        income = self.incomes_keeper.received(sender_node_id, task_id, subtask_id, transaction_id, value)
        with db.atomic():
            # Matching received but too early to check
            self.assertEquals(ExpectedIncome.select().count(), 1)

            expected_income.modified_date = datetime.datetime.now() - datetime.timedelta(hours=1)
            expected_income.save()

        self.incomes_keeper.run_once()
        with db.atomic():
            # Match
            self.assertEquals(ExpectedIncome.select().count(), 0)
