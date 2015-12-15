import logging
from golem.transactions.transactionsystem import TransactionSystem
from golem.transactions.ethereum.ethereumpaymentskeeper import EthereumPaymentsKeeper
from ethereumconnector import EthereumConnector
from golem.core.variables import ETH_CONN_ADDR

log = logging.getLogger("golem.t.eth")


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """
    def __init__(self, node_id, eth_account):
        """ Create new transaction system instance for node with given id
        :param node_id: id of a node that has this transaction system.
        :param eth_account: ethereum account address (bytes20)
        """
        log.info("Ethereum Transaction System created ({})".format(eth_account))
        TransactionSystem.__init__(self, node_id, EthereumPaymentsKeeper)
        self.eth_account = eth_account

    def global_pay_for_task(self, task_id, payments):
        """ Pay for task using Ethereum connector
        :param task_id: pay for task with given id
        :param dict payments: all payments group by ethereum address
        """
        eth_connector = EthereumConnector(ETH_CONN_ADDR)
        eth_connector.pay_for_task(self.eth_account, task_id, payments)
