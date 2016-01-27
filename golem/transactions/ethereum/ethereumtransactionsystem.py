import logging

from golem.transactions.transactionsystem import TransactionSystem
from golem.transactions.ethereum.ethereumpaymentskeeper import EthereumPaymentsKeeper, EthereumAddress
from ethereumconnector import EthereumConnector

from golem.core.variables import ETH_CONN_ADDR


logger = logging.getLogger(__name__)


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """
    def __init__(self, node_id, eth_account):
        """ Create new transaction system instance for node with given id
        :param node_id: id of a node that has this transaction system.
        :param eth_account: ethereum account address (bytes20)
        """
        TransactionSystem.__init__(self, node_id, EthereumPaymentsKeeper)
        self.eth_account = EthereumAddress(eth_account)

    def global_pay_for_task(self, task_id, payments):
        """ Pay for task using Ethereum connector
        :param task_id: pay for task with given id
        :param dict payments: all payments group by ethereum address
        """
        eth_connector = EthereumConnector(ETH_CONN_ADDR)
        if self.eth_account.get_str_addr():
            eth_connector.pay_for_task(self.eth_account.get_str_addr(), task_id, payments)
        else:
            logger.warning("[!IMPORTANT!] Can't pay for task {}, no ethereum address set".format(task_id))

    def get_eth_account(self):
        return self.eth_account.get_str_addr()



