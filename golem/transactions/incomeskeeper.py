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

    def start(self):
        pass

    def stop(self):
        pass

    def run_once(self):
        delta = datetime.datetime.now() - datetime.timedelta(minutes=10)
        with db.atomic():
            expected_incomes = ExpectedIncome\
                    .select()\
                    .where(ExpectedIncome.modified_date < delta)\
                    .order_by(-ExpectedIncome.id)\
                    .limit(50)\
                    .execute()

            for expected_income in expected_incomes:
                is_subtask_paid = Income.select().where(
                    Income.sender_node == expected_income.sender_node,
                    Income.subtask == expected_income.subtask)\
                    .exists()

                if is_subtask_paid:
                    expected_income.delete_instance()

                else:  # ask for payment
                    expected_income.modified_date = datetime.datetime.now()
                    expected_income.save()
                    dispatcher.send(
                        signal="golem.transactions",
                        event="expected_income",
                        expected_income=expected_income)

    def received(self,
                 sender_node_id,
                 subtask_id,
                 transaction_id,
                 value):

        try:
            with db.transaction():
                expected_income = \
                    ExpectedIncome.get(sender_node=sender_node_id,
                                       subtask=subtask_id)
                expected_income.delete_instance()

        except ExpectedIncome.DoesNotExist:
            logger.info("ExpectedIncome.DoesNotExist "
                        "(sender_node_id %r, "
                        "subtask_id %r, value %r) ",
                        sender_node_id, subtask_id, value)

        try:
            with db.transaction():
                income = Income.create(
                    sender_node=sender_node_id,
                    subtask=subtask_id,
                    transaction=transaction_id,
                    value=value)
                return income

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

    def expect(self, sender_node_id, p2p_node, subtask_id, value):
        logger.debug(
            "expect(%r, %r, %r)",
            sender_node_id,
            subtask_id,
            value
        )
        return ExpectedIncome.create(
            sender_node=sender_node_id,
            sender_node_details=p2p_node,
            subtask=subtask_id,
            value=value
        )

    def update_awaiting(self, subtask_id, accepted_ts):
        try:
            # FIXME: query by (sender_id, subtask_id)
            income = ExpectedIncome.get(subtask=subtask_id)
        except ExpectedIncome.DoesNotExist:
            logger.error(
                "ExpectedIncome.DoesNotExist subtask_id: %r",
                subtask_id)
            return
        income.accepted_ts = accepted_ts
        income.save()

    def get_list_of_all_incomes(self):
        # TODO: pagination
        union = ExpectedIncome.select(
            ExpectedIncome.created_date,
            ExpectedIncome.sender_node,
            ExpectedIncome.subtask,
            peewee.SQL("NULL as 'transaction'"),
            ExpectedIncome.value
        ) | Income.select(
            Income.created_date,
            Income.sender_node,
            Income.subtask,
            Income.transaction,
            Income.value
        )

        # Usage of .c : http://docs.peewee-orm.com/en/latest/peewee
        # /querying.html#using-subqueries
        return union.order_by(union.c.created_date.desc()).execute()
