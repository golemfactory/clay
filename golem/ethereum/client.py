import logging

import rlp
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
            Client.node.start(rpc=True)
        self.web3 = Web3(KeepAliveRPCProvider(host='localhost', port=Client.node.rpcport))

    @staticmethod
    def _kill_node():
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
        return self.web3.eth.getTransactionCount(address)

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
        return self.web3.eth.sendTransaction(transaction)

    def get_balance(self, account):
        """
        Returns the balance of the given account
        :param account: Account
        :return: Balance
        """
        return self.web3.eth.getBalance(account)

    def call(self, obj):
        """
        Executes a message call transaction, which is directly executed in the VM of the node,
        but never mined into the blockchain
        :param obj: A transaction object see web3.eth.sendTransaction, with the difference
        that for calls the from property is optional as well
        :return: The returned data of the call, e.g. a codes functions return value
        """
        return self.web3.eth.call(obj)

    def get_transaction_receipt(self, hash):
        """
        Returns the receipt of a transaction by transaction hash.
        :param hash: The transaction hash
        :return: Receipt of a transaction
        """
        return self.web3.eth.getTransactionReceipt(hash)

    def new_filter(self, array):
        """ https://github.com/ethereum/wiki/wiki/JavaScript-API#web3ethfilter """
        return self.web3.eth.filter(array)
