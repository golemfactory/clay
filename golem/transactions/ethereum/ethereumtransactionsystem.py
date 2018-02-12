import logging
import random

from ethereum.utils import privtoaddr
from eth_utils import encode_hex

from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumpaymentskeeper \
    import EthereumAddress
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem
import golem_sci

log = logging.getLogger('golem.pay')


NODE_LIST = [
    'http://188.165.227.180:55555',
    'http://94.23.17.170:55555',
    'http://94.23.57.58:55555',
]


def get_public_nodes():
    """Returns public geth RPC addresses"""
    addr_list = NODE_LIST[:]
    random.shuffle(addr_list)
    return addr_list


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

        def tx_sign(tx):
            tx.sign(node_priv_key)
        eth_address = encode_hex(privtoaddr(node_priv_key))

        self._node = None
        if start_geth:
            self._node = NodeProcess(datadir)
            ipc_path = self._node.start(start_port)
            sci = golem_sci.new_sci_ipc(ipc_path, eth_address, tx_sign)
            log.info('Connected to local Geth')
        else:
            addresses = [address] if address else get_public_nodes()
            sci = None
            for addr in addresses:
                try:
                    sci = golem_sci.new_sci_rpc(addr, eth_address, tx_sign)
                    log.info('Connected to remote Geth at %r', addr)
                    break
                except Exception as e:
                    log.warning(e)
            if sci is None:
                raise Exception('Could not connect to remote Geth')

        self.payment_processor = PaymentProcessor(sci=sci, faucet=True)

        super().__init__(incomes_keeper=EthereumIncomesKeeper(sci))

        self.payment_processor.start()

    def stop(self):
        if self.payment_processor.running:
            self.payment_processor.stop()
        self.incomes_keeper.stop()
        if self._node:
            self._node.stop()

    def add_payment_info(self, *args, **kwargs):
        payment = super().add_payment_info(*args, **kwargs)
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
