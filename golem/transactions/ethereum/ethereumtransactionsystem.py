import logging
from time import sleep

from ethereum.utils import privtoaddr

from golem.ethereum import Client
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.report import report_calls, Component
from golem.transactions.ethereum.ethereumpaymentskeeper \
    import EthereumAddress
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem
from golem.utils import encode_hex

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key):
        """ Create new transaction system instance for node with given id
        :param node_priv_key str: node's private key for Ethereum account (32b)
        """

        # FIXME: Passing private key all around might be a security issue.
        #        Proper account managment is needed.

        try:
            node_address = privtoaddr(node_priv_key)
        except AssertionError:
            raise ValueError("not a valid private key")

        self.__eth_addr = EthereumAddress(node_address)
        if self.get_payment_address() is None:
            raise ValueError("Invalid Ethereum address constructed '{}'"
                             .format(node_address))

        log.info("Node Ethereum address: " + self.get_payment_address())

        payment_processor = PaymentProcessor(
            client=Client(datadir),
            privkey=node_priv_key,
            faucet=True
        )

        super(EthereumTransactionSystem, self).__init__(
            incomes_keeper_class=EthereumIncomesKeeper(
                payment_processor)
        )

        self.incomes_keeper.start()

    def stop(self):
        self.incomes_keeper.stop()

    def add_payment_info(self, *args, **kwargs):
        payment = super(EthereumTransactionSystem, self).add_payment_info(
            *args,
            **kwargs
        )
        self.incomes_keeper.processor.add(payment)
        return payment

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return self.__eth_addr.get_str_addr()

    def get_balance(self):
        if not self.incomes_keeper.processor.balance_known():
            return None, None, None
        gnt = self.incomes_keeper.processor.gnt_balance()
        av_gnt = self.incomes_keeper.processor._gnt_available()
        eth = self.incomes_keeper.processor.eth_balance()
        return gnt, av_gnt, eth

    @report_calls(Component.ethereum, 'sync')
    def sync(self):
        syncing = True
        while syncing:
            try:
                # syncing = self.__eth_node.is_syncing() # old one

                syncing = self.incomes_keeper.processor.\
                    _PaymentProcessor__client.is_syncing()  # todo GG
                # syncing = self.incomes_keeper.processor.synchronized()
            except Exception as e:
                log.error("IPC error: {}".format(e))
                syncing = False
            else:
                sleep(0.5)
