import logging
from time import sleep

from ethereum.utils import privtoaddr

from golem.ethereum import Client
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.ethereum.token import GNTToken
from golem.report import report_calls, Component
from golem.transactions.ethereum.ethereumpaymentskeeper \
    import EthereumAddress
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key, port=None, start_geth=False):
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

        client = Client(datadir, port, start_geth)
        token = GNTToken(client)
        payment_processor = PaymentProcessor(
            client=client,
            privkey=node_priv_key,
            token=token,
            faucet=True
        )

        super(EthereumTransactionSystem, self).__init__(
            incomes_keeper=EthereumIncomesKeeper(
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
                syncing = self.incomes_keeper.processor.is_synchronized()
            except Exception as e:
                log.error("IPC error: {}".format(e))
                syncing = False
            else:
                sleep(0.5)
