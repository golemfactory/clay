# -*- coding: utf-8 -*-

import logging

from golem_messages.utils import bytes32_to_uuid

from golem.model import GenericKeyValue
from golem.transactions.incomeskeeper import IncomesKeeper

logger = logging.getLogger(__name__)


class EthereumIncomesKeeper(IncomesKeeper):
    BLOCK_NUMBER_DB_KEY = 'eth_incomes_keeper_block_number'
    BLOCK_NUMBER_BUFFER = 50

    def __init__(self, sci) -> None:
        self.__sci = sci

        values = GenericKeyValue.select().where(
            GenericKeyValue.key == self.BLOCK_NUMBER_DB_KEY)
        from_block = int(values.get().value) if values.count() == 1 else 0
        self.__sci.subscribe_to_batch_transfers(
            None,
            self.__sci.get_eth_address(),
            from_block,
            self._on_batch_event,
        )

        # Temporary try-catch block, until GNTDeposit is deployed on mainnet.
        # Remove it after that.
        try:
            self.__sci.subscribe_to_forced_subtask_payments(
                None,
                self.__sci.get_eth_address(),
                from_block,
                self._on_forced_subtask_payment,
            )
        except AttributeError as e:
            logger.info("Can't use GNTDeposit on mainnet yet: %r", e)

    def _on_batch_event(self, event):
        self.received_batch_transfer(
            event.tx_hash,
            event.sender,
            event.amount,
            event.closure_time,
        )

    def _on_forced_subtask_payment(self, event):
        self.received_forced_subtask_payment(
            event.tx_hash,
            event.requestor,
            str(bytes32_to_uuid(event.subtask_id)),
            event.amount,
        )

    def stop(self) -> None:
        block_number = self.__sci.get_block_number()
        if block_number:
            with GenericKeyValue._meta.database.transaction():
                kv, _ = GenericKeyValue.get_or_create(
                    key=self.BLOCK_NUMBER_DB_KEY)
                kv.value = block_number - self.BLOCK_NUMBER_BUFFER
                kv.save()
        super().stop()
