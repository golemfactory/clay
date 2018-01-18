# -*- coding: utf-8 -*-

import logging

from golem.model import db
from golem import model
from golem.model import Income
from golem.transactions.incomeskeeper import IncomesKeeper

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):

    def __init__(self, eth_address: str, token) -> None:
        self.__eth_address = eth_address
        self.__token = token

    def received(self,
                 sender_node_id,
                 task_id,
                 subtask_id,
                 transaction_id,
                 block_number,
                 value):

        logger.debug('MY ADDRESS: %r', self.__eth_address)

        if not self.__token.is_synchronized():
            logger.warning("token must be synchronized with "
                           "blockchain, otherwise income may not be found."
                           "Please wait until synchronized")
            self.__token.wait_until_synchronized()

        incomes = self.__token.get_incomes_from_block(
            block_number,
            self.__eth_address)
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
        return super().received(
            sender_node_id=sender_node_id,
            task_id=task_id,
            subtask_id=subtask_id,
            transaction_id=transaction_id,
            block_number=block_number,
            value=value
        )
