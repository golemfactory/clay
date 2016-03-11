import logging

from ethereum import keys

from golem.transactions.transactionsystem import TransactionSystem
from .ethereumpaymentskeeper import EthereumPaymentsKeeper

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
        self.__node_priv_key = node_priv_key
        self.__node_address = keys.privtoaddr(node_priv_key)
        logger.info("Node Ethereum address: " + self.get_payment_address())

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return '0x' + self.__node_address.encode('hex')

    def global_pay_for_task(self, task_id, payments):
        """ Pay for task using Ethereum connector
        :param task_id: pay for task with given id
        :param dict payments: all payments group by ethereum address
        """
