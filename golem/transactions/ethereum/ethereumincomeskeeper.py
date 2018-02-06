# -*- coding: utf-8 -*-

import logging

from ethereum.utils import denoms, sha3

from golem.model import ExpectedIncome, GenericKeyValue
from golem.transactions.incomeskeeper import IncomesKeeper
from golem.utils import decode_hex

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):
    REQUIRED_CONFS = 6
    BLOCK_NUMBER_DB_KEY = 'eth_incomes_keeper_block_number'
    BLOCK_NUMBER_BUFFER = 10

    def __init__(self, eth_address: str, sci) -> None:
        self.__eth_address = eth_address
        self.__sci = sci

        values = GenericKeyValue.select().where(
            GenericKeyValue.key == self.BLOCK_NUMBER_DB_KEY)
        from_block = int(values.get().value) if values.count() == 1 else 0
        self.__sci.subscribe_to_incoming_batch_transfers(
            eth_address,
            from_block,
            self._on_batch_event,
            self.REQUIRED_CONFS,
        )

    def _on_batch_event(self, event):
        expected = ExpectedIncome.select().where(
            ExpectedIncome.accepted_ts > 0,
            ExpectedIncome.accepted_ts <= event.closure_time)

        def is_sender(sender_node):
            return sha3(decode_hex(sender_node))[12:] == \
                decode_hex(event.sender)
        expected = [e for e in expected if is_sender(e.sender_node)]
        expected_value = sum([e.value for e in expected])
        if expected_value == 0:
            # Probably already handled event
            return

        if expected_value != event.amount:
            # Need to report this to Concent if expected is greater
            # and probably move all these expected incomes to a different table
            logger.warning(
                'Batch transfer amount does not match, expected %r, got %r',
                expected_value / denoms.ether,
                event.amount / denoms.ether)

        amount_left = event.amount

        for e in expected:
            value = min(amount_left, e.value)
            amount_left -= value
            self.received(
                sender_node_id=e.sender_node,
                subtask_id=e.subtask,
                transaction_id=event.tx_hash,
                value=value,
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
