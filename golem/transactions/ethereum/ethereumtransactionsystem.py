import logging
from os import path

from ethereum import keys

from golem.ethereum import Client
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.ethereum.paymentmonitor import PaymentMonitor
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
        if not isinstance(node_priv_key, basestring) or len(node_priv_key) != 32:
            raise ValueError("Invalid private key: {}".format(node_priv_key))
        self.__node_address = keys.privtoaddr(node_priv_key)
        log.info("Node Ethereum address: " + self.get_payment_address())

        datadir = path.join(datadir, "ethereum")
        eth_node = Client()
        self.__proc = PaymentProcessor(eth_node, node_priv_key, faucet=True)
        self.__proc.start()
        self.__monitor = PaymentMonitor(eth_node, self.__node_address)
        self.__monitor.start()
        # TODO: We can keep address in PaymentMonitor only

    def add_payment_info(self, *args, **kwargs):
        payment = super(EthereumTransactionSystem, self).add_payment_info(*args, **kwargs)
        self.__proc.add(payment)

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return '0x' + self.__node_address.encode('hex')

    def get_balance(self):
        if not self.__proc.balance_known():
            return None, None, None
        gnt = self.__proc.gnt_balance()
        av_gnt = self.__proc._gnt_available()
        eth = self.__proc.eth_balance()
        return gnt, av_gnt, eth

    def pay_for_task(self, task_id, payments):
        """ Pay for task using Ethereum connector
        :param task_id: pay for task with given id
        :param dict payments: all payments group by ethereum address
        """
        pass

    def get_incoming_payments(self):
        return [{'status': payment.status.value,
                 'payer': payment.payer,
                 'value': payment.value,
                 'block_number': payment.extra['block_number']
                 } for payment in self.__monitor.get_incoming_payments()]
