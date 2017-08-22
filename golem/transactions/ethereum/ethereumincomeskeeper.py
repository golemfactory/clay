# -*- coding: utf-8 -*-

import logging
import peewee

from golem import model
from golem.transactions.incomeskeeper import IncomesKeeper
from golem.ethereum import Client
from golem.ethereum.paymentprocessor import PaymentProcessor

logger = logging.getLogger('golem.transactions.ethereum.ethereumincomeskeeper')


class EthereumIncomesKeeper(IncomesKeeper):
    LOG_ID = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'  # noqa

    # Contrary to documentation sqlite3 overflows over signed word (int32_t)
    # (Documentation writes about double word int64_t)
    # http://www.sqlite.org/datatype3.html
    SQLITE3_MAX_INT = 2**31 - 1

    def __init__(self, processor: PaymentProcessor):
        self.processor = processor

    def start(self):
        self.processor.start()

    def stop(self):
        self.processor.stop()


    def _wtf(self, from_block=None, to_block=None, address=None, topics=None):

            from calendar import timegm
            from datetime import datetime
            import pytz

            from ethereum.utils import zpad
            from web3 import Web3, HTTPProvider, IPCProvider

            from time import sleep
            web3 = Web3(IPCProvider('/home/ggruszczynski/.ethereum/rinkeby/geth.ipc'))
            latest_block = web3.eth.getBlock('latest')

            def is_syncing():
                def get_timestamp_utc():
                    now = datetime.now(pytz.utc)
                    return datetime_to_timestamp(now)

                def datetime_to_timestamp(then):
                    return timegm(then.utctimetuple()) + then.microsecond / 1000000.0

                """
                :return: Returns either False if the node is not syncing, True otherwise
                """
                syncing = web3.eth.syncing
                if syncing:
                    return syncing['currentBlock'] < syncing['highestBlock']

                # node may not have started syncing yet
                try:
                    last_block = web3.eth.getBlock('latest')
                except Exception as ex:
                    return False
                if isinstance(last_block, dict):
                    timestamp = int(last_block['timestamp'])
                else:
                    timestamp = last_block.timestamp
                return get_timestamp_utc() - timestamp > 120

            syncing = True
            while syncing:
                try:
                    syncing = is_syncing()
                    print('syncing...')
                except Exception as e:
                    syncing = False
                else:
                    sleep(0.5)

            print('--------------- synced ----------------')

            def new_filter(from_block="latest", to_block="latest", address=None, topics=None):
                """
                Creates a filter object, based on filter options, to notify when the state changes (logs)
                :param from_block: Integer block number, or "latest" for the last mined block
                or "pending", "earliest" for not yet mined transactions
                :param to_block: Integer block number, or "latest" for the last mined block
                or "pending", "earliest" for not yet mined transactions
                :param address: Contract address or a list of addresses from which logs should originate
                :param topics: Array of 32 Bytes DATA topics. Topics are order-dependent.
                Each topic can also be an array of DATA with "or" options
                :return: filter id
                """
                if topics is not None:
                    for i in range(len(topics)):
                        topics[i] = add_padding(topics[i])
                obj = {
                    'fromBlock': from_block,
                    'toBlock': to_block,
                    'address': add_padding(address),
                    'topics': topics
                }
                return web3.eth.filter(obj).filter_id

            def get_logs(from_block=None, to_block=None, address=None, topics=None):
                """
                Retrieves logs based on filter options
                :param from_block: Integer block number, or "latest" for the last mined block
                or "pending", "earliest" for not yet mined transactions
                :param to_block: Integer block number, or "latest" for the last mined block
                or "pending", "earliest" for not yet mined transactions
                :param address: Contract address or a list of addresses from which logs should originate
                :param topics: Array of 32 Bytes DATA topics. Topics are order-dependent.
                Each topic can also be an array of DATA with "or" options
                topic[hash, from, to]
                The first topic is the hash of the signature of the event (e.g. Deposit(address,bytes32,uint256)), except you declared the event with the anonymous specifier.)
                :return: Returns log entries described by filter options
                """
                for i in range(len(topics)):
                    topics[i] = add_padding(topics[i])
                filter_id = new_filter(from_block, to_block, add_padding(address), topics)
                return web3.eth.getFilterLogs(filter_id)

            def add_padding(address):
                """
                Provide proper length of address and add 0x to it
                :param address: Address to validation
                :return: Padded address
                """
                if address is None:
                    return address
                elif isinstance(address, str):
                    address = address.encode()
                if isinstance(address, bytes):
                    if address.startswith(b'0x'):
                        return address
                    return b'0x' + zpad(address, 32)
                    raise TypeError('Address must be a string or a byte string')

            block_info = web3.eth.getBlock(from_block)
            income_log = get_logs(from_block=from_block,
                              to_block=to_block,
                              topics=topics)

            return income_log



    def received(self, sender_node_id, task_id, subtask_id, transaction_id,
                 block_number, value):
        my_address = self.processor.eth_address()
        logger.debug('MY ADDRESS: %r', my_address)

        # my_address2 =self.processor.eth_address_new()

        # GG todo - make sure its synced!!!
        from time import sleep
        is_synchronized = False
        while not is_synchronized:
            try:
                is_synchronized = self.processor.synchronized()
            except Exception as e:
                logger.error("payment reception failed "
                             "while syncing with eth blockchain: "
                             "{}".format(e))
                is_synchronized = False
            else:
                sleep(0.5)

        incomes = self.processor.get_logs(
            from_block=block_number,
            to_block=block_number,
            topics=[self.LOG_ID, None, my_address]
        )

        block_info = self.processor._PaymentProcessor__client.web3.eth.getBlock(block_number)


        incomes2 = self._wtf(
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
