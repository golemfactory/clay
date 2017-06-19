# -*- coding: utf-8 -*-

import logging
import peewee

from golem import model
from golem.transactions.incomeskeeper import IncomesKeeper

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):
    LOG_ID = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'  # noqa

    # Contrary to documentation sqlite3 overflows over signed word (int32_t)
    # (Documentation writes about double word int64_t)
    # http://www.sqlite.org/datatype3.html
    SQLITE3_MAX_INT = 2**31 - 1

    def received(self, sender_node_id, task_id, subtask_id, transaction_id,
                 block_number, value):
        my_address = self.processor.eth_address()
        logger.debug('MY ADDRESS: %r', my_address)
        incomes = self.eth_node.get_logs(
            from_block=block_number,
            to_block=block_number,
            topics=[self.LOG_ID, None, my_address]
        )
        if not incomes:
            logger.error('Transaction not present: %r', transaction_id)
            return
        received_tokens = 0
        # FIXME sum() will overflow if it becomes bigger than 8 bytes
        # signed int
        spent_tokens = model.Income.select(peewee.fn.sum(model.Income.value))\
            .where(model.Income.transaction == transaction_id)\
            .scalar(convert=True)
        if spent_tokens is None:
            spent_tokens = 0
        received_tokens -= spent_tokens
        for income_log in incomes:
            # Should we verify sender address?
            sender = income_log['topics'][1][-40:]
            receiver = income_log['topics'][2][-40:]
            log_value = long(income_log['data'], 16)
            logger.debug(
                'INCOME: from %r to %r v:%r',
                sender,
                receiver,
                log_value
            )
            # Count tokens only when we're the receiver.
            if receiver == my_address:
                received_tokens += log_value
        if received_tokens >= self.SQLITE3_MAX_INT:
            logger.error(
                "Too many tokens received in transaction %r!"
                "%r will overflow db.",
                transaction_id,
                received_tokens
            )
            desc = "Too many tokens received: {}".format(received_tokens)
            raise OverflowError(desc)
        if received_tokens < value:
            logger.error(
                "Not enough tokens received for subtask: %r."
                "expected: %r got: %r",
                subtask_id,
                value,
                received_tokens
            )
            return
        logger.debug('received_tokens: %r', received_tokens)
        return super(EthereumIncomesKeeper, self).received(
            sender_node_id=sender_node_id,
            task_id=task_id,
            subtask_id=subtask_id,
            transaction_id=transaction_id,
            block_number=block_number,
            value=value
        )
