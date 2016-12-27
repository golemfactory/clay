import logging

import rlp
from ethereum.transactions import Transaction
from web3 import Web3, KeepAliveRPCProvider

from .node import NodeProcess

log = logging.getLogger('golem.ethereum')


class Client(object):
    """ RPC interface client for Ethereum node."""

    STATIC_NODES = ["enode://f1fbbeff7e9777a3a930f1e55a5486476845f799f7d603f71be7b00898df98f2dc2e81b854d2c774c3d266f1fa105d130d4a43bc58e700155c4565726ae6804e@94.23.17.170:30900"]  # noqa

    node = None

    def __init__(self, datadir, nodes=None):
        if not nodes:
            nodes = Client.STATIC_NODES
        if not Client.node:
            Client.node = NodeProcess(nodes, datadir)
        else:
            assert Client.node.datadir == datadir, \
                "Ethereum node's datadir cannot be changed"
        if not Client.node.is_running():
            Client.node.start(rpc=True, mining=True)
        self.web3 = Web3(KeepAliveRPCProvider(host='localhost', port=Client.node.rpcport))

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
        return bool(self.web3.eth.syncing)

    def get_transaction_count(self, address):
        """
        Returns the number of transactions that have been sent from account
        :param address: account address
        :return: number of transactions
        """
        return self.web3.eth.getTransactionCount(Client.__add_padding(address))

    def send_raw_transaction(self, data):
        """
        Sends a signed and serialized transaction
        :param data: signed and serialized transaction
        """
        return self.web3.eth.sendRawTransaction(data)

    def send(self, transaction):
        """
        Signs and sends the given transaction
        :param transaction: http://web3py.readthedocs.io/en/latest/web3.eth.html
        """
        if isinstance(transaction, Transaction):
            raw_data = rlp.encode(transaction)
            hex_data = self.web3.toHex(raw_data)
            return self.send_raw_transaction(hex_data)
        return self.web3.eth.sendTransaction(transaction)

    def get_balance(self, account, block_identifier=None):
        """
        Returns the balance of the given account at the block specified by block_identifier
        :param account: The address to get the balance of
        :param block_identifier: If you pass this parameter it will not use the default block
        set with web3.eth.defaultBlock
        :return: Balance
        """
        return self.web3.eth.getBalance(Client.__add_padding(account), block_identifier or self.web3.eth.defaultBlock)

    def call(self, _from=None, to=None, gas=90000, gas_price=3000, value=0, data=None, nonce=0, block=None):
        """
        Executes a message call transaction, which is directly executed in the VM of the node,
        but never mined into the blockchain
        :param _from: The address for the sending account
        :param to: The destination address of the message, left undefined for a contract-creation transaction
        :param gas: The value transferred for the transaction in Wei,
        also the endowment if it's a contract-creation transaction
        :param gas_price: The amount of gas to use for the transaction (unused gas is refunded)
        :param value: The price of gas for this transaction in wei, defaults to the mean network gas price
        :param data: Either a byte string containing the associated data of the message,
        or in the case of a contract-creation transaction, the initialisation code
        :param nonce: Integer of a nonce. This allows to overwrite your own pending transactions that use the same nonce
        :param block: integer block number, or the string "latest", "earliest" or "pending"
        :return: The returned data of the call, e.g. a codes functions return value
        """
        _from = Client.__add_padding(_from) or self.web3.eth.defaultAccount
        block = block or self.web3.eth.defaultBlock

        obj = {
            'from': _from,
            'to': to,
            'gas': gas,
            'gasPrice': gas_price,
            'value': value,
            'data': data,
            'nonce': nonce
        }
        return self.web3.eth.call(obj, block)

    def get_transaction_receipt(self, tx_hash):
        """
        Returns the receipt of a transaction by transaction hash.
        :param tx_hash: The transaction hash
        :return: Receipt of a transaction
        """
        return self.web3.eth.getTransactionReceipt(tx_hash)

    def new_filter(self, from_block="latest", to_block="latest", address=None, topics=None):
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
            for i in xrange(len(topics)):
                topics[i] = Client.__add_padding(topics[i])
        obj = {
            'fromBlock': from_block,
            'toBlock': to_block,
            'address': Client.__add_padding(address),
            'topics': topics
        }
        return self.web3.eth.filter(obj).filter_id

    def get_filter_changes(self, filer_id):
        """
        Polling method for a filter, which returns an array of logs which occurred since last poll
        :param filer_id: the filter id
        :return: Returns all new entries which occurred since the last call to this method for the given filter_id
        """
        return self.web3.eth.getFilterChanges(Client.__add_padding(filer_id))

    def get_logs(self, from_block=None, to_block=None, address=None, topics=None):
        """
        Retrieves logs based on filter options
        :param from_block: Integer block number, or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param to_block: Integer block number, or "latest" for the last mined block
        or "pending", "earliest" for not yet mined transactions
        :param address: Contract address or a list of addresses from which logs should originate
        :param topics: Array of 32 Bytes DATA topics. Topics are order-dependent.
        Each topic can also be an array of DATA with "or" options
        :return: Returns log entries described by filter options
        """
        for i in xrange(len(topics)):
            topics[i] = Client.__add_padding(topics[i])
        filter_id = self.new_filter(from_block, to_block, Client.__add_padding(address), topics)
        return self.web3.eth.getFilterLogs(filter_id)

    @staticmethod
    def __add_padding(address):
        """
        Provide proper length of address and add 0x to it
        :param address: Address to validation
        :return: Padded address
        """
        from eth_abi.utils import zpad
        if address is None:
            return address
        elif isinstance(address, basestring):
            if address.startswith('0x'):
                return address
            return '0x' + zpad(address, 32)
        raise TypeError('Address must be a string')
