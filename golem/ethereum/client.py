import logging

import rlp
from eth_rpc_client import Client as EthereumRpcClient

from .node import NodeProcess

log = logging.getLogger('golem.ethereum')


class Client(EthereumRpcClient):

    STATIC_NODES = ["enode://f1fbbeff7e9777a3a930f1e55a5486476845f799f7d603f71be7b00898df98f2dc2e81b854d2c774c3d266f1fa105d130d4a43bc58e700155c4565726ae6804e@94.23.17.170:30900"]  # noqa

    node = None

    def __init__(self, datadir=None):
        if not Client.node:
            if datadir:
                Client.node = NodeProcess(Client.STATIC_NODES, datadir)
            else:
                Client.node = NodeProcess(Client.STATIC_NODES)
        elif datadir:
            assert Client.node.datadir == datadir
        if not Client.node.is_running():
            Client.node.start(rpc=True)
        super(Client, self).__init__(port=Client.node.rpcport)

    @staticmethod
    def _kill_node():
        # FIXME: Keeping the node as a static object might not be the best.
        if Client.node:
            Client.node.stop()
            Client.node = None

    def get_peer_count(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#net_peerCount
        """
        response = self.make_request("net_peerCount", [])
        return int(response['result'], 16)

    def is_syncing(self):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_syncing
        """
        response = self.make_request("eth_syncing", [])
        result = response['result']
        return bool(result)

    def get_transaction_count(self, address):
        """
        https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_gettransactioncount
        """
        response = self.make_request("eth_getTransactionCount", [address, "pending"])
        return int(response['result'], 16)

    def send_raw_transaction(self, data):
        response = self.make_request("eth_sendRawTransaction", [data])
        return response['result']

    def send(self, transaction):
        return self.send_raw_transaction(rlp.encode(transaction).encode('hex'))
