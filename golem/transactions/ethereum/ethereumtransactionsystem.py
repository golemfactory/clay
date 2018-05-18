import logging
from typing import List, Optional

from ethereum.utils import privtoaddr, denoms
from eth_utils import encode_hex, is_address

from golem_sci import new_sci, chains
from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.ethereum.exceptions import NotEnoughFunds
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

    def sync(self) -> None:
        self.payment_processor.sync()

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

    def eth_for_batch_payment(self, num_payments: int) -> int:
        return self.payment_processor.get_gas_cost_per_payment() * num_payments

    def eth_base_for_batch_payment(self):
        return self.payment_processor.ETH_BATCH_PAYMENT_BASE

    def get_withdraw_gas_cost(self, amount: int, currency: str) -> int:
        gas_price = self._sci.get_current_gas_price()
        if currency == 'ETH':
            return 21000 * gas_price
        if currency == 'GNT':
            total_gnt = \
                self.payment_processor._gnt_available()  # pylint: disable=W0212
            gnt = self._sci.get_gnt_balance(self._sci.get_eth_address())
            gntb = total_gnt - gnt
            if gnt >= amount:
                return self._sci.GAS_GNT_TRANSFER * gas_price
            if gntb >= amount:
                return self._sci.GAS_WITHDRAW * gas_price
            return (self._sci.GAS_GNT_TRANSFER + self._sci.GAS_WITHDRAW) \
                * gas_price
        raise ValueError('Unknown currency {}'.format(currency))

    def withdraw(
            self,
            amount: int,
            destination: str,
            currency: str,
            lock: int = 0) -> List[str]:
        if not is_address(destination):
            raise ValueError("{} is not valid ETH address".format(destination))

        pp = self.payment_processor
        if currency == 'ETH':
            eth = pp._eth_available()  # pylint: disable=W0212
            if amount > eth - lock:
                raise NotEnoughFunds(amount, eth - lock, currency)
            log.info(
                "Withdrawing %f ETH to %s",
                amount / denoms.ether,
                destination,
            )
            return [self._sci.transfer_eth(destination, amount)]

        if currency == 'GNT':
            total_gnt = pp._gnt_available()  # pylint: disable=W0212
            if amount > total_gnt - lock:
                raise NotEnoughFunds(amount, total_gnt - lock, currency)
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

    def concent_balance(self) -> int:
        return self._sci.get_deposit_value(
            account_address=self._sci.get_eth_address(),
        )

    def concent_deposit(
            self, required: int, expected: int, reserved: int) -> Optional[str]:
        current = self.concent_balance()
        if current >= required:
            return None
        required -= current
        expected -= current
        # TODO migrate funds from gnt to gntb
        gntb_balance = self._sci.get_gntb_balance(self._sci.get_eth_address())
        gntb_balance -= reserved
        if gntb_balance < required:
            raise NotEnoughFunds(required, gntb_balance, 'GNTB')
        max_possible_amount = min(expected, gntb_balance)
        transaction_id = self._sci.deposit_payment(max_possible_amount)
        return transaction_id
