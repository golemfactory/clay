import logging
from typing import List

from ethereum.utils import privtoaddr, denoms
from eth_utils import encode_hex

from golem_sci import new_sci, chains
from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.transactionsystem import TransactionSystem

log = logging.getLogger('golem.pay')


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key, mainnet=False, start_geth=False,  # noqa pylint: disable=too-many-arguments
                 start_port=None, address=None):
        """ Create new transaction system instance for node with given id
        :param node_priv_key str: node's private key for Ethereum account(32b)
        """

        try:
            eth_addr = encode_hex(privtoaddr(node_priv_key))
        except AssertionError:
            raise ValueError("not a valid private key")
        log.info("Node Ethereum address: %s", eth_addr)

        self._node = NodeProcess(datadir, mainnet, start_geth, address)
        self._node.start(start_port)
        self._sci = new_sci(
            self._node.web3,
            eth_addr,
            lambda tx: tx.sign(node_priv_key),
            chains.MAINNET if mainnet else chains.RINKEBY,
        )
        self.payment_processor = PaymentProcessor(
            sci=self._sci,
            faucet=not mainnet,
        )

        super().__init__(
            incomes_keeper=EthereumIncomesKeeper(self._sci),
        )

        self.payment_processor.start()

    def stop(self):
        if self.payment_processor.running:
            self.payment_processor.stop()
        self.incomes_keeper.stop()
        self._sci.stop()
        self._node.stop()

    def add_payment_info(self, *args, **kwargs):
        payment = super().add_payment_info(*args, **kwargs)
        self.payment_processor.add(payment)
        return payment

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return self._sci.get_eth_address()

    def get_balance(self):
        if not self.payment_processor.balance_known():
            return None, None, None, None, None
        gnt, last_gnt_update = self.payment_processor.gnt_balance()
        av_gnt = self.payment_processor._gnt_available()
        eth, last_eth_update = self.payment_processor.eth_balance()
        return gnt, av_gnt, eth, last_gnt_update, last_eth_update

    def eth_for_batch_payment(self, num_payments):
        return self.payment_processor.ETH_BATCH_PAYMENT_BASE + \
            self.payment_processor.ETH_PER_PAYMENT * num_payments

    def withdraw(
            self,
            amount: int,
            destination: str,
            currency: str,
            lock: int = 0) -> List[str]:
        pp = self.payment_processor
        if currency == 'ETH':
            eth = pp._eth_available()  # pylint: disable=W0212
            if amount > eth - lock:
                raise ValueError('Not enough ETH available')
            log.info(
                "Withdrawing %f ETH to %s",
                amount / denoms.ether,
                destination,
            )
            return [self._sci.transfer_eth(destination, amount)]

        if currency == 'GNT':
            total_gnt = pp._gnt_available()  # pylint: disable=W0212
            if amount > total_gnt - lock:
                raise ValueError('Not enough GNT available')
            gnt = self._sci.get_gnt_balance(self._sci.get_eth_address())
            gntb = total_gnt - gnt

            if gnt >= amount:
                log.info(
                    "Withdrawing %f GNT to %s",
                    amount / denoms.ether,
                    destination,
                )
                return [self._sci.transfer_gnt(destination, amount)]

            if gntb >= amount:
                log.info(
                    "Withdrawing %f GNTB to %s",
                    amount / denoms.ether,
                    destination,
                )
                return [self._sci.convert_gntb_to_gnt(destination, amount)]

            log.info(
                "Withdrawing %f GNT and %f GNTB to %s",
                gnt / denoms.ether,
                (amount - gnt) / denoms.ether,
                destination,
            )
            res = []
            res.append(self._sci.transfer_gnt(destination, gnt))
            amount -= gnt
            res.append(self._sci.convert_gntb_to_gnt(destination, amount))
            return res

        raise ValueError('Unknown currency {}'.format(currency))
