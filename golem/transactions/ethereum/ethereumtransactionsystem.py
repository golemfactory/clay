import logging
from os import path

from ethereum import keys

from golem.ethereum import Client
from golem.transactions.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.transactionsystem import TransactionSystem

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key):
        """ Create new transaction system instance for node with given id
        :param node_priv_key str: node's private key for Ethereum account (32b)
        """
        super(EthereumTransactionSystem, self).__init__()

        # FIXME: Passing private key all around might be a security issue.
        #        Proper account managment is needed.
        assert type(node_priv_key) is str and len(node_priv_key) is 32
        self.__node_address = keys.privtoaddr(node_priv_key)
        log.info("Node Ethereum address: " + self.get_payment_address())

        datadir = path.join(datadir, "ethereum")
        eth_node = Client(datadir=datadir)
        self.__proc = PaymentProcessor(eth_node, node_priv_key, faucet=True)

    def add_payment_info(self, *args, **kwargs):
        payment = super(EthereumTransactionSystem, self).add_payment_info(*args, **kwargs)
        self.__proc.add(payment)

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return '0x' + self.__node_address.encode('hex')

    def pay_for_task(self, task_id, payments):
        """ Pay for task using Ethereum connector
        :param task_id: pay for task with given id
        :param dict payments: all payments group by ethereum address
        """
        pass
