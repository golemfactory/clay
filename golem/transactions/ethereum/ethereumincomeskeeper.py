# -*- coding: utf-8 -*-

import logging
import peewee

from time import sleep
from golem.model import db
from golem import model
from golem.model import Income
from golem.transactions.incomeskeeper import IncomesKeeper
from golem.ethereum.paymentprocessor import PaymentProcessor

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):
    LOG_ID = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'  # noqa

    def __init__(self, processor: PaymentProcessor) -> None:
        self.processor = processor

    def start(self):
        self.processor.start()

    def stop(self):
        if self.processor.running:
            self.processor.stop()

    def received(self,
                 sender_node_id,
                 task_id,
                 subtask_id,
                 transaction_id,
                 block_number,
                 value):

        my_address = self.processor.eth_address()
        logger.debug('MY ADDRESS: %r', my_address)

        if not self.processor.is_synchronized():
            logger.warning("payment processor must be synchronized with "
                           "blockchain, otherwise income may not be found."
                           "Please wait until synchronized")
            self.processor.wait_until_synchronized()

        incomes = self.processor.get_logs(
            from_block=block_number,
            to_block=block_number,
            topics=[self.LOG_ID, None, my_address])

        if not incomes:
            logger.error('Transaction not present in blockchain: %r',
                         transaction_id)
            return

        # Prevent using the same payment for another subtask
        try:
            with db.transaction():
                spent_tokens = \
                    model.Income.select().where(
                        model.Income.transaction == transaction_id).get().value
        except Income.DoesNotExist:
            spent_tokens = 0

        # FIXME in Brass:
        # currently our db doesnt support partial payments for subtasks,
        # ie Income primary_key = CompositeKey('sender_node', 'subtask')
        # watch out: peewee sum() may:
        # 1) overflow if it becomes bigger than 8 bytes
        # 2) cannot sum strings (value is encoded to hex then saved to db)

        received_tokens = 0
        received_tokens -= spent_tokens
        for income_log in incomes:
            # Should we verify sender address?
            sender = income_log['topics'][1]
            receiver = income_log['topics'][2]
            log_value = int(income_log['data'], 16)
            logger.debug(
                'INCOME: from %r to %r v:%r',
                sender,
                receiver,
                log_value
            )
            # Count tokens only when we're the receiver.
            if receiver == my_address:
                received_tokens += log_value
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
