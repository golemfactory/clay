import logging
import time
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import List

from ethereum.utils import privtoaddr, denoms
from eth_utils import encode_hex, is_address, to_checksum_address
import requests

from golem_sci import new_sci
from golem.config.active import ETHEREUM_CHAIN, ETHEREUM_FAUCET_ENABLED
from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.ethereum import exceptions
from golem.transactions.transactionsystem import TransactionSystem

log = logging.getLogger('golem.pay')


class ConversionStatus(Enum):
    NONE = 0
    OPENING_GATE = 1
    TRANSFERRING = 2
    UNFINISHED = 3


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
            Path(datadir),
            self._node.web3,
            eth_addr,
            lambda tx: tx.sign(node_priv_key),
            ETHEREUM_CHAIN,
        )
        self._faucet = ETHEREUM_FAUCET_ENABLED
        self._gnt_faucet_requested = False

        self._gnt_conversion_status = ConversionStatus.NONE
        gate_address = self._sci.get_gate_address()
        if gate_address is not None:
            if self._sci.get_gnt_balance(gate_address):
                self._gnt_conversion_status = ConversionStatus.UNFINISHED

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

    def get_withdraw_gas_cost(
            self,
            amount: int,
            destination: str,
            currency: str) -> int:
        gas_price = self._sci.get_current_gas_price()
        if currency == 'ETH':
            return self._sci.estimate_transfer_eth_gas(destination, amount) * \
                gas_price
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
                raise exceptions.NotEnoughFunds(amount, eth - lock, currency)
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
                raise exceptions.NotEnoughFunds(
                    amount,
                    total_gnt - lock,
                    currency,
                )
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
            self,
            required: int,
            expected: int,
            reserved: int,
            cb=None) -> None:
        if cb is None:
            def noop():
                pass
            cb = noop
        current = self.concent_balance()
        if current >= required:
            cb()
            return
        required -= current
        expected -= current
        gntb_balance = self._gntb_balance
        gntb_balance -= reserved
        if gntb_balance < required:
            raise exceptions.NotEnoughFunds(required, gntb_balance, 'GNTB')
        max_possible_amount = min(expected, gntb_balance)
        tx_hash = self._sci.deposit_payment(max_possible_amount)
        log.info(
            "Requested concent deposit of %.6fGNT (tx: %r)",
            max_possible_amount / denoms.ether,
            tx_hash,
        )

        def transaction_receipt(receipt):
            if not receipt.status:
                log.critical("Deposit failed. Receipt: %r", receipt)
                return
            cb()

        self._sci.on_transaction_confirmed(tx_hash, transaction_receipt)

    def _get_funds_from_faucet(self) -> None:
        if not self._faucet or not self._balance_known():
            return
        if self._eth_balance < 0.01 * denoms.ether:
            log.info("Requesting tETH from faucet")
            tETH_faucet_donate(self._sci.get_eth_address())
            return

        if self._gnt_balance + self._gntb_balance < 100 * denoms.ether:
            if not self._gnt_faucet_requested:
                log.info("Requesting GNT from faucet")
                self._sci.request_gnt_from_faucet()
                self._gnt_faucet_requested = True
        else:
            self._gnt_faucet_requested = False

    def _balance_known(self) -> bool:
        return self._last_eth_update is not None and \
            self._last_gnt_update is not None

    def _refresh_balances(self) -> None:
        addr = self._sci.get_eth_address()

        self._eth_balance = self._sci.get_eth_balance(addr)
        self._last_eth_update = time.mktime(datetime.today().timetuple())

        self._gnt_balance = self._sci.get_gnt_balance(addr)
        self._gntb_balance = self._sci.get_gntb_balance(addr)
        self._last_gnt_update = time.mktime(datetime.today().timetuple())

    def _try_convert_gnt(self) -> None:  # pylint: disable=too-many-branches
        if not self._balance_known():
            return
        if self._gnt_conversion_status == ConversionStatus.UNFINISHED:
            if self._gnt_balance > 0:
                self._gnt_conversion_status = ConversionStatus.NONE
            else:
                gas_cost = self._sci.get_current_gas_price() * \
                    self._sci.GAS_TRANSFER_FROM_GATE
                if self._eth_balance >= gas_cost:
                    tx_hash = self._sci.transfer_from_gate()
                    log.info(
                        "Finishing previously started GNT conversion %s",
                        tx_hash,
                    )
                    self._gnt_conversion_status = ConversionStatus.TRANSFERRING
                else:
                    log.info(
                        "Not enough gas to finish GNT conversion, has %.6f,"
                        " needed: %.6f",
                        self._eth_balance / denoms.ether,
                        gas_cost / denoms.ether,
                    )
            return
        if self._gnt_balance == 0:
            self._gnt_conversion_status = ConversionStatus.NONE
            return

        gas_price = self._sci.get_current_gas_price()
        gate_address = self._sci.get_gate_address()
        if gate_address is None:
            gas_cost = gas_price * self._sci.GAS_OPEN_GATE
            if self._gnt_conversion_status != ConversionStatus.OPENING_GATE:
                if self._eth_balance >= gas_cost:
                    tx_hash = self._sci.open_gate()
                    log.info("Opening GNT-GNTB conversion gate %s", tx_hash)
                    self._gnt_conversion_status = ConversionStatus.OPENING_GATE
                else:
                    log.info(
                        "Not enough gas for opening conversion gate, has: %.6f,"
                        " needed: %.6f",
                        self._eth_balance / denoms.ether,
                        gas_cost / denoms.ether,
                    )
            return

        # This is extra safety check, shouldn't ever happen
        if int(gate_address, 16) == 0:
            log.critical('Gate address should not equal to %s', gate_address)
            return

        if self._gnt_conversion_status == ConversionStatus.OPENING_GATE:
            self._gnt_conversion_status = ConversionStatus.NONE

        gas_cost = gas_price * \
            (self._sci.GAS_GNT_TRANSFER + self._sci.GAS_TRANSFER_FROM_GATE)
        if self._gnt_conversion_status != ConversionStatus.TRANSFERRING:
            if self._eth_balance >= gas_cost:
                tx_hash1 = \
                    self._sci.transfer_gnt(gate_address, self._gnt_balance)
                tx_hash2 = self._sci.transfer_from_gate()
                log.info(
                    "Converting %.6f GNT to GNTB %s %s",
                    self._gnt_balance / denoms.ether,
                    tx_hash1,
                    tx_hash2,
                )
                self._gnt_conversion_status = ConversionStatus.TRANSFERRING
            else:
                log.info(
                    "Not enough gas for GNT conversion, has: %.6f,"
                    " needed: %.6f",
                    self._eth_balance / denoms.ether,
                    gas_cost / denoms.ether,
                )

    def _run(self) -> None:
        self._refresh_balances()
        self._get_funds_from_faucet()
        self._try_convert_gnt()
        self.payment_processor.sendout()


def tETH_faucet_donate(addr: str):
    request = "http://188.165.227.180:4000/donate/{}".format(addr)
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
