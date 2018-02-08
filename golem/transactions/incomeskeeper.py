# -*- coding: utf-8 -*-
import logging

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
        # TODO Check for unpaid incomes and ask Concent for them
        pass

    def received(self,
                 sender_node_id,
                 subtask_id,
                 transaction_id,
                 value) -> None:

        with Income._meta.database.transaction():
            try:
                income = Income.get(
                    sender_node=sender_node_id,
                    subtask=subtask_id,
                )
            except Income.DoesNotExist:
                logger.info("Income.DoesNotExist "
                            "(sender_node_id %r, "
                            "subtask_id %r, value %r) ",
                            sender_node_id, subtask_id, value)
                return
            income.transaction = transaction_id[2:]
            income.value = value
            income.save()

    def expect(self, sender_node_id, subtask_id, value):
        logger.debug(
            "expect(%r, %r, %r)",
            sender_node_id,
            subtask_id,
            value
        )
        return Income.create(
            sender_node=sender_node_id,
            subtask=subtask_id,
            value=value
        )

    def update_awaiting(self, subtask_id, accepted_ts):
        try:
            # FIXME: query by (sender_id, subtask_id)
            income = Income.get(subtask=subtask_id)
        except Income.DoesNotExist:
            logger.error(
                "Income.DoesNotExist subtask_id: %r",
                subtask_id)
            return
        income.accepted_ts = accepted_ts
        income.save()

    def get_list_of_all_incomes(self):
        # TODO: pagination
        return Income.select(
            Income.created_date,
            Income.sender_node,
            Income.subtask,
            Income.transaction,
            Income.value
        ).order_by(Income.created_date.desc())
