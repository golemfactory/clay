# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import logging
import time
from typing import List

from ethereum.utils import denoms
from pydispatch import dispatcher

from golem.core.variables import PAYMENT_DEADLINE
from golem.model import Income
from golem.utils import encode_hex, pubkeytoaddr

logger = logging.getLogger("golem.transactions.incomeskeeper")


class IncomesKeeper:
    """Keeps information about payments received from other nodes
    """

    def start(self):
        pass

    def stop(self):
        pass

    def run_once(self):
        # TODO Check for unpaid incomes and ask Concent for them. issue #2194
        pass

    def received_batch_transfer(self, tx_hash, sender, amount, closure_time):
        expected = Income.select().where(
            Income.accepted_ts > 0,
            Income.accepted_ts <= closure_time,
            Income.transaction.is_null())
        expected = \
            [e for e in expected if pubkeytoaddr(e.sender_node) == sender]

        expected_value = sum([e.value for e in expected])
        if expected_value == 0:
            # Probably already handled event
            return

        if expected_value != amount:
            # TODO Need to report this to Concent if expected is greater
            # and probably move all these expected incomes to a different table
            # issue #2255
            logger.warning(
                'Batch transfer amount does not match, expected %r, got %r',
                expected_value / denoms.ether,
                amount / denoms.ether)

        amount_left = amount

        for e in expected:
            value = min(amount_left, e.value)
            amount_left -= value
            e.transaction = tx_hash[2:]
            # TODO don't change the value, wait for Concent. issue #2255
            e.value = value
            e.save()

        dispatcher.send(
            signal='golem.monitor',
            event='income',
            addr=encode_hex(sender),
            value=amount
        )

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

    def update_awaiting(self, sender_node, subtask_id, accepted_ts):
        try:
            income = Income.get(sender_node=sender_node, subtask=subtask_id)
        except Income.DoesNotExist:
            logger.error(
                "Income.DoesNotExist subtask_id: %r",
                subtask_id)
            return
        if income.accepted_ts is not None and income.accepted_ts != accepted_ts:
            logger.error(
                "Duplicated accepted_ts %r for %r",
                accepted_ts,
                income,
            )
            return
        income.accepted_ts = accepted_ts
        income.save()

    def get_list_of_all_incomes(self):
        # TODO: pagination. issue #2402
        return Income.select(
            Income.created_date,
            Income.sender_node,
            Income.subtask,
            Income.transaction,
            Income.value
        ).order_by(Income.created_date.desc())

    @staticmethod
    def update_overdue_incomes() -> List[Income]:
        """
        Set overdue flag for all incomes that have been waiting for too long.
        :return: Updated incomes
        """
        accepted_ts_deadline = int(time.time()) - PAYMENT_DEADLINE
        created_deadline = datetime.now() - timedelta(seconds=PAYMENT_DEADLINE)

        incomes = list(Income.select().where(
            Income.overdue == False,   # noqa pylint: disable=singleton-comparison
            Income.transaction.is_null(True),
            (Income.accepted_ts < accepted_ts_deadline) | (
                Income.accepted_ts.is_null(True) &
                (Income.created_date < created_deadline)
            )
        ))
        for income in incomes:
            income.overdue = True
            income.save()
        return incomes
