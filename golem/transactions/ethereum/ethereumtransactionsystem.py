import logging
from time import sleep

from ethereum.utils import privtoaddr

from golem.ethereum import Client
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.report import report_calls, Component
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, account_password: bytes, port=None):
        """ Create new transaction system instance for node with given id
        :param account_password bytes: password for Ethereum account
        """

        payment_processor = PaymentProcessor(
            Client(datadir, port),
            account_password,
            faucet=True
        )

        super(EthereumTransactionSystem, self).__init__(
            incomes_keeper=EthereumIncomesKeeper(payment_processor)
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
        return '0x' + self.__proc.account.address.hex()

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
