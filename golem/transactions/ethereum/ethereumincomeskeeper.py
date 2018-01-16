# -*- coding: utf-8 -*-

import logging

from golem import model
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.model import Income
from golem.transactions.incomeskeeper import IncomesKeeper

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):

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

        incomes = self.processor.get_incomes_from_block(block_number,
                                                        my_address)
        if not incomes:
            logger.error('Transaction not present in blockchain: %r',
                         transaction_id)
            return

        # Prevent using the same payment for another subtask
        try:
            spent_tokens = model.Income.select()\
                .where(model.Income.transaction == transaction_id)\
                .get().value
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
        for income in incomes:
            # Should we verify sender address?
            sender = income['sender']
            income_value = income['value']
            logger.debug(
                'INCOME: from %r v:%r',
                sender,
                income_value
            )
            received_tokens += income_value
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
