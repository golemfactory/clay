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
