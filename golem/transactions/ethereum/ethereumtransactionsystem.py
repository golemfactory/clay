import logging

from golem.transactions.transactionsystem import TransactionSystem
from golem.transactions.ethereum.ethereumpaymentskeeper import EthereumPaymentsKeeper, EthereumAddress
from ethereumconnector import EthereumConnector

from golem.core.variables import ETH_CONN_ADDR


logger = logging.getLogger(__name__)


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """
    def __init__(self, node_id, node_priv_key):
        """ Create new transaction system instance for node with given id
        :param node_id: id of a node that has this transaction system.
        :param node_priv_key str: node's private key for Ethereum account (32b)
        """
        TransactionSystem.__init__(self, node_id, EthereumPaymentsKeeper)
        # FIXME: Passing private key all around might be a security issue.
        #        Proper account managment is needed.
        assert type(node_priv_key) is str and len(node_priv_key) is 32
        self.eth_account = EthereumAddress.from_priv_key(node_priv_key)

    def global_pay_for_task(self, task_id, payments):
        """ Pay for task using Ethereum connector
        :param task_id: pay for task with given id
        :param dict payments: all payments group by ethereum address
        """
        eth_connector = EthereumConnector(ETH_CONN_ADDR)
        if self.eth_account.get_str_addr():
            eth_connector.pay_for_task(self.eth_account.get_str_addr(), task_id, payments)
        else:
            # FIXME Proper way of dealing with empty Ethereum address should be implemented
            logger.warning("Can't pay for task {}, no ethereum address set".format(task_id))

    def get_eth_account(self):
        return self.eth_account.get_str_addr()
