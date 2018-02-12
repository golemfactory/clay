# -*- coding: utf-8 -*-

import logging

from golem.model import GenericKeyValue
from golem.transactions.incomeskeeper import IncomesKeeper

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):
    REQUIRED_CONFS = 6
    BLOCK_NUMBER_DB_KEY = 'eth_incomes_keeper_block_number'
    BLOCK_NUMBER_BUFFER = 10

    def __init__(self, sci) -> None:
        self.__sci = sci

        values = GenericKeyValue.select().where(
            GenericKeyValue.key == self.BLOCK_NUMBER_DB_KEY)
        from_block = int(values.get().value) if values.count() == 1 else 0
        self.__sci.subscribe_to_incoming_batch_transfers(
            self.__sci.get_eth_address(),
            from_block,
            self._on_batch_event,
            self.REQUIRED_CONFS,
        )

    def _on_batch_event(self, event):
        self.received_batch_transfer(
            event.tx_hash,
            event.sender,
            event.amount,
            event.closure_time,
        )

    def stop(self) -> None:
        block_number = self.__sci.get_block_number()
        if block_number:
            with GenericKeyValue._meta.database.transaction():
                kv, _ = GenericKeyValue.get_or_create(
                    key=self.BLOCK_NUMBER_DB_KEY)
                kv.value = block_number - self.REQUIRED_CONFS -\
                    self.BLOCK_NUMBER_BUFFER
                kv.save()
        super().stop()
