import logging

from time import sleep
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

        self.__eth_node = Client()
        self.__proc = PaymentProcessor(self.__eth_node, node_priv_key, faucet=True)
        self.__proc.start()
        self.__monitor = PaymentMonitor(self.__eth_node, self.__node_address)
        self.__monitor.start()
        # TODO: We can keep address in PaymentMonitor only

    def stop(self):
        if self.__proc.running:
            self.__proc.stop()
        if self.__monitor.running:
            self.__monitor.stop()
        if self.__eth_node.node is not None:
            self.__eth_node.node.stop()

    def add_payment_info(self, *args, **kwargs):
        payment = super(EthereumTransactionSystem, self).add_payment_info(*args, **kwargs)
        self.__proc.add(payment)
        return payment

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

    def get_incoming_payments(self):
        return [{'status': payment.status.value,
                 'payer': payment.payer,
                 'value': payment.value,
                 'block_number': payment.extra['block_number']
                 } for payment in self.__monitor.get_incoming_payments()]

    def sync(self):
        syncing = True
        while syncing:
            try:
                syncing = self.__eth_node.is_syncing()
            except Exception as e:
                log.error("IPC error: {}".format(e))
                syncing = False
            else:
                sleep(0.5)
