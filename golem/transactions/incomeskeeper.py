# -*- coding: utf-8 -*-
import datetime
import logging
import peewee
from pydispatch import dispatcher

from golem.model import db
from golem.model import ExpectedIncome
from golem.model import Income

logger = logging.getLogger("golem.transactions.incomeskeeper")


class IncomesKeeper(object):
    """Keeps information about payments received from other nodes
    """
    def run_once(self):
        delta = datetime.datetime.now() - datetime.timedelta(minutes=10)
        with db.atomic():
            for expected_income in ExpectedIncome\
                    .select()\
                    .where(ExpectedIncome.modified_date < delta)\
                    .order_by(-ExpectedIncome.id).limit(50):
                try:
                    with db.atomic():
                        Income.get(
                            sender_node=expected_income.sender_node,
                            task=expected_income.task,
                            subtask=expected_income.subtask,
                        )
                except Income.DoesNotExist:
                    # Income is still expected.
                    with db.atomic():
                        expected_income.modified_date = datetime.datetime.now()
                        expected_income.save()
                    dispatcher.send(
                        signal="golem.transactions",
                        event="expected_income",
                        expected_income=expected_income
                    )
                    continue
                expected_income.delete_instance()

    def received(self, sender_node_id, task_id, subtask_id, transaction_id,
                 block_number, value):
        try:
            with db.transaction():
                expected_income = ExpectedIncome.get(subtask=subtask_id)
        except ExpectedIncome.DoesNotExist:
            expected_income = None
        try:
            with db.transaction():
                return Income.create(
                    sender_node=sender_node_id,
                    task=task_id,
                    subtask=subtask_id,
                    transaction=transaction_id,
                    block_number=block_number,
                    value=value
                )
        except peewee.IntegrityError:
            db_income = Income.get(
                sender_node=sender_node_id,
                subtask=subtask_id
            )
            logger.error(
                'Duplicated entry for subtask: %r %dwGNT (tx: %r, dbtx: %r)',
                subtask_id,
                value,
                transaction_id,
                db_income.transaction
            )
        if expected_income:
            expected_income.delete()

    def expect(self, sender_node_id, p2p_node, task_id, subtask_id, value):
        logger.debug(
            "expect(%r, %r, %r, %r)",
            sender_node_id,
            task_id,
            subtask_id,
            value
        )
        return ExpectedIncome.create(
            sender_node=sender_node_id,
            sender_node_details=p2p_node,
            task=task_id,
            subtask=subtask_id,
            value=value
        )
