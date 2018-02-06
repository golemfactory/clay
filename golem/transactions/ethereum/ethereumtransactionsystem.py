import logging

from ethereum.utils import privtoaddr

from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumpaymentskeeper \
    import EthereumAddress
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem
import golem_sci

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key, start_geth=False,  # noqa pylint: disable=too-many-arguments
                 start_port=None, address=None):
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

        self._node = NodeProcess(datadir, start_geth, address)
        self._node.start(start_port)
        self._sci = golem_sci.new_testnet(self._node.web3)
        self.payment_processor = PaymentProcessor(
            privkey=node_priv_key,
            sci=self._sci,
            faucet=True
        )

        super().__init__(
            incomes_keeper=EthereumIncomesKeeper(
                self.payment_processor.eth_address(),
                self._sci)
        )

        self.payment_processor.start()

    def stop(self):
        if self.payment_processor.running:
            self.payment_processor.stop()
        self.incomes_keeper.stop()
        self._node.stop()

    def add_payment_info(self, *args, **kwargs):
        payment = super(EthereumTransactionSystem, self).add_payment_info(
            *args,
            **kwargs
        )
        self.payment_processor.add(payment)
        return payment

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return self.__eth_addr.get_str_addr()

    def get_balance(self):
        if not self.payment_processor.balance_known():
            return None, None, None
        gnt = self.payment_processor.gnt_balance()
        av_gnt = self.payment_processor._gnt_available()
        eth = self.payment_processor.eth_balance()
        return gnt, av_gnt, eth
