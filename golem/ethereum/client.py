import logging
import time

import rlp
from ethereum.utils import zpad

from golem.core.common import get_timestamp_utc
from .node import NodeProcess

log = logging.getLogger('golem.ethereum')


class Client(object):
    """ RPC interface client for Ethereum node."""

    node = None

    SYNC_CHECK_INTERVAL = 10

    def __init__(self, datadir, start_node=False, start_port=None,
                 address=None):
        if not Client.node:
            Client.node = NodeProcess(datadir, address, start_node)
        if not Client.node.is_running():
            Client.node.start(start_port)
        self.web3 = Client.node.web3
        # Set fake default account.
        self.web3.eth.defaultAccount = '\xff' * 20
        self._last_sync_check = time.time()
        self._sync = False
        self._temp_sync = False

    @staticmethod
    def _kill_node():
        """
        Stop node if is running
        """
        # FIXME: Keeping the node as a static object might not be the best.
        if Client.node:
            Client.node.stop()
            Client.node = None

    def get_peer_count(self):
        """
        Get peers count
        :return: The number of peers currently connected to the client
        """
        return self.web3.net.peerCount

    def is_syncing(self):
        """
        :return: Returns either False if the node is not syncing, True otherwise
        """
        syncing = self.web3.eth.syncing
        if syncing:
            return syncing['currentBlock'] < syncing['highestBlock']

        # node may not have started syncing yet
        try:
            last_block = self.web3.eth.getBlock('latest')
        except Exception as ex:
            log.debug(ex)
            return False
        if isinstance(last_block, dict):
            timestamp = int(last_block['timestamp'])
        else:
            timestamp = last_block.timestamp
        return get_timestamp_utc() - timestamp > 120

    def get_transaction_count(self, address):
        """
        Returns the number of transactions that have been sent from account.
        Use `pending` block to account the transactions that haven't been mined
        yet. Otherwise it would be problematic to send more than one transaction
        in less than ~15 seconds span.
        :param address: account address
        :return: number of transactions
        """
        return self.web3.eth.getTransactionCount(Client.__add_padding(address),
                                                 'pending')

    def send(self, transaction):
        """
        Sends signed Ethereum transaction.
        :return The 32 Bytes transaction hash as HEX string
        """
        raw_data = rlp.encode(transaction)
        hex_data = self.web3.toHex(raw_data)
        return self.web3.eth.sendRawTransaction(hex_data)

    def get_balance(self, account, block=None):
        """
        Returns the balance of the given account
        at the block specified by block_identifier
        :param account: The address to get the balance of
        :param block: If you pass this parameter
        it will not use the default block
        set with web3.eth.defaultBlock
        :return: Balance
        """
        try:
            return self.web3.eth.getBalance(account, block)
        except ValueError as e:
            log.error("Ethereum RPC: {}".format(e))
            return None

    def call(self, _from=None, to=None, gas=90000, gas_price=3000, value=0,
             data=None, block=None):
        """
        Executes a message call transaction,
        which is directly executed in the VM of the node,
        but never mined into the blockchain
        :param _from: The address for the sending account
        :param to: The destination address of the message,
        left undefined for a contract-creation transaction
        :param gas: The value transferred for the transaction in Wei,
        also the endowment if it's a contract-creation transaction
        :param gas_price:
        The amount of gas to use for the transaction
        (unused gas is refunded)
        :param value:
        The price of gas for this transaction in wei,
        defaults to the mean network gas price
        :param data:
        Either a byte string containing the associated data of the message,
        or in the case of a contract-creation transaction,
        the initialisation code
        :param block:
        integer block number,
        or the string "latest", "earliest" or "pending"
        :return:
        The returned data of the call,
        e.g. a codes functions return value
        """
        obj = {
            'from': _from,
            'to': to,
            'gas': gas,
            'gasPrice': gas_price,
            'value': value,
            'data': data,
        }
        return self.web3.eth.call(obj, block)

    def get_block_number(self):
        return self.web3.eth.blockNumber

    def get_transaction_receipt(self, tx_hash):
        """
        Returns the receipt of a transaction by transaction hash.
        :param tx_hash: The transaction hash
        :return: Receipt of a transaction
        """
        return self.web3.eth.getTransactionReceipt(tx_hash)

    def new_filter(self, from_block="latest", to_block="latest", address=None,
                   topics=None):
        """
        Creates a filter object, based on filter options,
        to notify when the state changes (logs)
        :param from_block:
        Integer block number, or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param to_block:
        Integer block number, or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param address:
        Contract address or a list of addresses from which logs should originate
        :param topics:
        Array of 32 Bytes DATA topics. Topics are order-dependent.
        Each topic can also be an array of DATA with "or" options
        :return: filter id
        """
        if topics is not None:
            for i in range(len(topics)):
                topics[i] = Client.__add_padding(topics[i])
        obj = {
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': address,
            'topics': topics
        }
        return self.web3.eth.filter(obj).filter_id

    def get_filter_changes(self, filer_id):
        """
        Polling method for a filter,
        which returns an array of logs which occurred since last poll
        :param filer_id: the filter id
        :return:
        Returns all new entries which occurred since the
        last call to this method for the given filter_id
        """
        return self.web3.eth.getFilterChanges(Client.__add_padding(filer_id))

    def get_logs(self,
                 from_block=None,
                 to_block=None,
                 address=None,
                 topics=None):
        """
        Retrieves logs based on filter options
        :param from_block: Integer block number,
        or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param to_block: Integer block number,
        or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param address:
        Contract address or a list of addresses from which logs should originate
        :param topics:
        Array of 32 Bytes DATA topics.
        Topics are order-dependent.
        Each topic can also be an array of DATA with "or" options
        topic[hash, from, to]
        The first topic is the hash of the signature of the event
        (e.g. Deposit(address,bytes32,uint256)),
        except you declared the event with the anonymous specifier.)
        :return: Returns log entries described by filter options
        """
        for i in range(len(topics)):
            topics[i] = Client.__add_padding(topics[i])
        filter_id = self.new_filter(from_block, to_block, address, topics)
        return self.web3.eth.getFilterLogs(filter_id)

    def wait_until_synchronized(self) -> bool:
        is_synchronized = False
        while not is_synchronized:
            try:
                is_synchronized = self.is_synchronized()
            except Exception as e:
                log.error("Error "
                          "while syncing with eth blockchain: "
                          "{}".format(e))
                is_synchronized = False
            else:
                time.sleep(self.SYNC_CHECK_INTERVAL)

        return True

    def is_synchronized(self):
        """ Checks if the Ethereum node is in sync with the network."""
        if time.time() - self._last_sync_check <= self.SYNC_CHECK_INTERVAL:
            # When checking again within 10 s return previous status.
            # This also handles geth issue where synchronization starts after
            # 10 s since the node was started.
            return self._sync
        self._last_sync_check = time.time()

        def check():
            peers = self.get_peer_count()
            log.info("Peer count: {}".format(peers))
            if peers == 0:
                return False
            if self.is_syncing():
                log.info("Node is syncing...")
                syncing = self.web3.eth.syncing
                if syncing:
                    log.info("currentBlock: " + str(syncing['currentBlock']) +
                             "\t highestBlock:" + str(syncing['highestBlock']))
                return False
            return True

        # TODO: This can be improved now because we use Ethereum Ropsten.
        # Normally we should check the time of latest block, but Golem testnet
        # does not produce block regularly. The workaround is to wait for 2
        # confirmations.
        if not check():
            # Reset both sync flags. We have to start over.
            self._temp_sync = False
            self._sync = False
            return False

        if not self._temp_sync:
            # Set the first flag. We will check again in SYNC_CHECK_INTERVAL s.
            self._temp_sync = True
            return False

        if not self._sync:
            # Second confirmation of being in sync. We are sure.
            self._sync = True
            log.info("Synchronized!")

        return True

    @staticmethod
    def __add_padding(address):
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
