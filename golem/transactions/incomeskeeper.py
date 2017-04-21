import datetime
import logging
import peewee
from pydispatch import dispatcher

from golem.model import ReceivedPayment, db
from golem.model import ExpectedIncome
from golem.model import Income

logger = logging.getLogger("golem.transactions.incomeskeeper")


class IncomesKeeper(object):
    """Keeps information about payments received from other nodes
    """
    def run_once(self):
        with db.atomic():
            for expected_income in ExpectedIncome.select().where(ExpectedIncome.modified_date < datetime.datetime.now() - datetime.timedelta(minutes=1)).order_by(-ExpectedIncome.id).limit(1):
                try:
                    with db.atomic():
                        income = Income.get(
                            sender_node=expected_income.sender_node,
                            task=expected_income.task,
                            subtask=expected_income.subtask,
                        )
                except Income.DoesNotExist:
                    # Income is still expected.
                    with db.atomic():
                        expected_income.modified_date = datetime.datetime.now()
                        expected_income.save()
                    dispatcher.send(signal="golem.transactions", event="expected_income", expected_income=expected_income)
                    continue
                if income.value != expected_income.value:
                    logger.warning('subtask: %r expected.value %r != income.value %r', expected_income.subtask, expected_income.value, income.value)
                    continue
                expected_income.delete_instance()

    def received(self, sender_node_id, task_id, subtask_id, transaction_id, value):
        try:
            with db.transaction():
                return Income.create(sender_node=sender_node_id, task=task_id, subtask=subtask_id, transaction=transaction_id, value=value)
        except peewee.IntegrityError:
            db_income = Income.get(sender_node=sender_node_id, subtask=subtask_id)
            logger.error('Duplicated entry for subtask: %r %dwGNT (tx: %r, dbtx: %r)', subtask_id, value, transaction_id, db_income.transaction)

    def expect(self, sender_node_id, task_id, subtask_id, value):
        logger.debug("expect(%r, %r, %r, %r)", sender_node_id, task_id, subtask_id, value)
        return ExpectedIncome.create(sender_node=sender_node_id, task=task_id, subtask=subtask_id, value=value)
