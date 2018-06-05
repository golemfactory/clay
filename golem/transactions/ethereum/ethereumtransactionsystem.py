from datetime import datetime
import logging
import time
from typing import List, Optional

from ethereum.utils import privtoaddr, denoms
from eth_utils import encode_hex, is_address, to_checksum_address
import requests

from golem_sci import new_sci
from golem_sci.gntconverter import GNTConverter
from golem.config.active import ETHEREUM_CHAIN, ETHEREUM_FAUCET_ENABLED
from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.ethereum.exceptions import NotEnoughFunds
from golem.transactions.transactionsystem import TransactionSystem

log = logging.getLogger('golem.pay')

DONATE_URL_TEMPLATE = "http://188.165.227.180:4000/donate/{}"


def tETH_faucet_donate(addr: str):
    request = DONATE_URL_TEMPLATE.format(addr)
    resp = requests.get(request)
    if resp.status_code != 200:
        log.error("tETH Faucet error code %r", resp.status_code)
        return False
    response = resp.json()
    if response['paydate'] == 0:
        log.warning("tETH Faucet warning %r", response['message'])
        return False
    # The paydate is not actually very reliable, usually some day in the past.
    paydate = datetime.fromtimestamp(response['paydate'])
    amount = int(response['amount']) / denoms.ether
    log.info("Faucet: %.6f ETH on %r", amount, paydate)
    return True


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    def __init__(self, datadir, node_priv_key, start_geth=False,  # noqa pylint: disable=too-many-arguments
                 start_port=None, address=None):
        """ Create new transaction system instance for node with given id
        :param node_priv_key str: node's private key for Ethereum account(32b)
        """

        try:
            eth_addr = \
                to_checksum_address(encode_hex(privtoaddr(node_priv_key)))
        except AssertionError:
            raise ValueError("not a valid private key")
        log.info("Node Ethereum address: %s", eth_addr)

        self._node = NodeProcess(datadir, start_geth, address)
        self._node.start(start_port)
        self._sci = new_sci(
            self._node.web3,
            eth_addr,
            lambda tx: tx.sign(node_priv_key),
            ETHEREUM_CHAIN,
        )
        self._gnt_converter = GNTConverter(self._sci)
        self._faucet = ETHEREUM_FAUCET_ENABLED
        self.payment_processor = PaymentProcessor(self._sci)

        super().__init__(
            incomes_keeper=EthereumIncomesKeeper(self._sci),
        )

        self._eth_balance: int = 0
        self._gnt_balance: int = 0
        self._gntb_balance: int = 0
        self._last_eth_update = None
        self._last_gnt_update = None
        self._is_stopped = False

    def stop(self):
        super().stop()
        self._is_stopped = True
        self.payment_processor.sendout(0)
        self.incomes_keeper.stop()
        self._sci.stop()
        self._node.stop()

    def sync(self) -> None:
        log.info("Synchronizing balances")
        self._sci.wait_until_synchronized()
        while not self._is_stopped:
            self._refresh_balances()
            if self._balance_known():
                log.info("Balances synchronized")
                return
            log.info("Waiting for initial GNT/ETH balances...")
            time.sleep(1)

    def add_payment_info(self, *args, **kwargs):
        payment = super().add_payment_info(*args, **kwargs)
        self.payment_processor.add(payment)
        return payment

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return self._sci.get_eth_address()

    def get_balance(self):
        if not self._balance_known():
            return None, None, None, None, None
        gnt_total = self._gnt_balance + self._gntb_balance
        gnt_av = gnt_total - self.payment_processor.reserved_gntb
        return gnt_total, gnt_av, self._eth_balance, \
            self._last_gnt_update, self._last_eth_update

    def eth_for_batch_payment(self, num_payments: int) -> int:
        return self.payment_processor.get_gas_cost_per_payment() * num_payments

    def eth_base_for_batch_payment(self):
        return self.payment_processor.ETH_BATCH_PAYMENT_BASE

    def get_withdraw_gas_cost(self, amount: int, currency: str) -> int:
        gas_price = self._sci.get_current_gas_price()
        if currency == 'ETH':
            return 21000 * gas_price
        if currency == 'GNT':
            return self._sci.GAS_WITHDRAW * gas_price
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
            eth = self._eth_balance - pp.reserved_eth
            if amount > eth - lock:
                raise NotEnoughFunds(amount, eth - lock, currency)
            log.info(
                "Withdrawing %f ETH to %s",
                amount / denoms.ether,
                destination,
            )
            return [self._sci.transfer_eth(destination, amount)]

        if currency == 'GNT':
            total_gnt = \
                self._gnt_balance + self._gntb_balance - pp.reserved_gntb
            if amount > total_gnt - lock:
                raise NotEnoughFunds(amount, total_gnt - lock, currency)
            # This can happen during unfinished GNT-GNTB conversion,
            # so we should wait until it finishes
            if amount > self._gntb_balance:
                raise Exception('Cannot withdraw right now, '
                                'background operations in progress')
            log.info(
                "Withdrawing %f GNTB to %s",
                amount / denoms.ether,
                destination,
            )
            return [self._sci.convert_gntb_to_gnt(destination, amount)]

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
        gntb_balance = self._gntb_balance
        gntb_balance -= reserved
        if gntb_balance < required:
            raise NotEnoughFunds(required, gntb_balance, 'GNTB')
        max_possible_amount = min(expected, gntb_balance)
        tx_hash = self._sci.deposit_payment(max_possible_amount)  # tx_hash
        log.info(
            "Requested concent deposit of %.6fGNT (tx: %r)",
            max_possible_amount,
            tx_hash,
        )
        return tx_hash

    def _get_ether_from_faucet(self) -> None:
        if not self._faucet or not self._balance_known():
            return
        if self._eth_balance < 0.01 * denoms.ether:
            log.info("Requesting tETH from faucet")
            tETH_faucet_donate(self._sci.get_eth_address())

    def _get_gnt_from_faucet(self) -> None:
        if not self._faucet or not self._balance_known():
            return
        if self._eth_balance < 0.001 * denoms.ether:
            return
        if self._gnt_balance + self._gntb_balance < 100 * denoms.ether:
            log.info("Requesting GNT from faucet")
            self._sci.request_gnt_from_faucet()

    def _balance_known(self) -> bool:
        return self._last_eth_update is not None and \
            self._last_gnt_update is not None

    def _refresh_balances(self) -> None:
        addr = self._sci.get_eth_address()

        eth_balance = self._sci.get_eth_balance(addr)
        if eth_balance is not None:
            self._eth_balance = eth_balance
            self._last_eth_update = time.mktime(datetime.today().timetuple())
        else:
            log.warning("Failed to retrieve ETH balance")

        gnt_balance = self._sci.get_gnt_balance(addr)
        if gnt_balance is not None:
            self._gnt_balance = \
                gnt_balance + self._gnt_converter.get_gate_balance()
        else:
            log.warning("Failed to retrieve GNT balance")

        gntb_balance = self._sci.get_gntb_balance(addr)
        if gntb_balance is not None:
            self._gntb_balance = gntb_balance
            # Update the last update time if both GNT and GNTB were updated
            if gnt_balance is not None:
                self._last_gnt_update = \
                    time.mktime(datetime.today().timetuple())
        else:
            log.warning("Failed to retrieve GNTB balance")

    def _run(self) -> None:
        self._refresh_balances()
        self._get_ether_from_faucet()
        self._get_gnt_from_faucet()

        if self._balance_known() and not self._gnt_converter.is_converting():
            if self._gnt_balance > 0 and self._eth_balance > 0:
                log.info(
                    "Converting %f GNT to GNTB",
                    self._gnt_balance / denoms.ether,
                )
                self._gnt_converter.convert(self._gnt_balance)

        self.payment_processor.run()
