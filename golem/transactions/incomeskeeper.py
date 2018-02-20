# -*- coding: utf-8 -*-
import logging

from ethereum.utils import denoms
from pydispatch import dispatcher

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
        # TODO Check for unpaid incomes and ask Concent for them
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
            # Need to report this to Concent if expected is greater
            # and probably move all these expected incomes to a different table
            logger.warning(
                'Batch transfer amount does not match, expected %r, got %r',
                expected_value / denoms.ether,
                amount / denoms.ether)

        amount_left = amount

        for e in expected:
            value = min(amount_left, e.value)
            amount_left -= value
            e.transaction = tx_hash[2:]
            e.value = value  # TODO don't change the value, wait for Concent
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

    def update_awaiting(self, subtask_id, accepted_ts):
        try:
            # FIXME: query by (sender_id, subtask_id)
            income = Income.get(subtask=subtask_id)
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
        # TODO: pagination
        return Income.select(
            Income.created_date,
            Income.sender_node,
            Income.subtask,
            Income.transaction,
            Income.value
        ).order_by(Income.created_date.desc())
