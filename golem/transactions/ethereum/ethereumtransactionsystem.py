import logging
import random
import time
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ethereum.utils import denoms
from eth_utils import is_address
import requests

from golem_sci import new_sci, JsonTransactionsStorage
from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.transactions.ethereum.ethereumincomeskeeper \
    import EthereumIncomesKeeper
from golem.transactions.ethereum.exceptions import NotEnoughFunds
from golem.transactions.transactionsystem import TransactionSystem
from golem.utils import privkeytoaddr

log = logging.getLogger(__name__)


class ConversionStatus(Enum):
    NONE = 0
    OPENING_GATE = 1
    TRANSFERRING = 2
    UNFINISHED = 3


class EthereumTransactionSystem(TransactionSystem):
    """ Transaction system connected with Ethereum """

    TX_FILENAME: ClassVar[str] = 'transactions.json'

    def __init__(
            self,
            datadir: str,
            node_priv_key: bytes,
            config) -> None:
        eth_addr = privkeytoaddr(node_priv_key)
        log.info("Node Ethereum address: %s", eth_addr)

        self._config = config

        node_list = config.NODE_LIST.copy()
        random.shuffle(node_list)
        node_list += config.FALLBACK_NODE_LIST
        self._node = NodeProcess(node_list)
        self._node.start()

        self._sci = new_sci(
            self._node.web3,
            eth_addr,
            config.CHAIN,
            JsonTransactionsStorage(Path(datadir) / self.TX_FILENAME),
            lambda tx: tx.sign(node_priv_key),
        )
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
        self._payments_locked: int = 0
        self._gntb_locked: int = 0

        self._refresh_balances()
        log.info(
            "Initial balances: %f GNTB, %f GNT, %f ETH",
            self._gntb_balance / denoms.ether,
            self._gnt_balance / denoms.ether,
            self._eth_balance / denoms.ether,
        )

    def stop(self):
        super().stop()
        self.payment_processor.sendout(0)
        self.incomes_keeper.stop()
        self._sci.stop()

    def add_payment_info(self, subtask_id: str, value: int, eth_address: str):
        payment = super().add_payment_info(subtask_id, value, eth_address)
        self.payment_processor.add(payment)
        return payment

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        return self._sci.get_eth_address()

    def get_available_eth(self) -> int:
        return self._eth_balance - self.get_locked_eth()

    def get_locked_eth(self) -> int:
        eth = self.payment_processor.reserved_eth + \
            self.eth_for_batch_payment(self._payments_locked)
        if self._payments_locked > 0 and \
           self.payment_processor.reserved_eth == 0:
            eth += self._eth_base_for_batch_payment()
        return min(eth, self._eth_balance)

    def get_available_gnt(self) -> int:
        return self._gntb_balance - self.get_locked_gnt()

    def get_locked_gnt(self) -> int:
        return self._gntb_locked + self.payment_processor.reserved_gntb

    def get_balance(self) -> Dict[str, Any]:
        return {
            'gnt_available': self.get_available_gnt(),
            'gnt_locked': self.get_locked_gnt(),
            'gnt_nonconverted': self._gnt_balance,
            'eth_available': self.get_available_eth(),
            'eth_locked': self.get_locked_eth(),
            'block_number': self._sci.get_block_number(),
            'gnt_update_time': self._last_gnt_update,
            'eth_update_time': self._last_eth_update,
        }

    def lock_funds_for_payments(self, price: int, num: int) -> None:
        gnt = price * num
        if gnt > self.get_available_gnt():
            raise NotEnoughFunds(gnt, self.get_available_gnt(), 'GNT')

        eth = self.eth_for_batch_payment(num)
        if self._payments_locked == 0 and \
           self.payment_processor.reserved_eth == 0:
            eth += self._eth_base_for_batch_payment()
        eth_available = self.get_available_eth()
        if eth > eth_available:
            raise NotEnoughFunds(eth, eth_available, 'ETH')

        log.info(
            "Locking %f GNT and ETH for %d payments",
            gnt / denoms.ether,
            num,
        )
        self._gntb_locked += gnt
        self._payments_locked += num

    def unlock_funds_for_payments(self, price: int, num: int) -> None:
        gnt = price * num
        if gnt > self._gntb_locked:
            raise Exception("Can't unlock {} GNT, locked: {}".format(
                gnt / denoms.ether,
                self._gntb_locked / denoms.ether,
            ))
        if num > self._payments_locked:
            raise Exception("Can't unlock {} payments, locked: {}".format(
                num,
                self._payments_locked,

            ))
        log.info(
            "Unlocking %f GNT and ETH for %d payments",
            gnt / denoms.ether,
            num,
        )
        self._gntb_locked -= gnt
        self._payments_locked -= num

    def eth_for_batch_payment(self, num_payments: int) -> int:
        return self.payment_processor.get_gas_cost_per_payment() * num_payments

    def _eth_base_for_batch_payment(self) -> int:
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
            currency: str) -> List[str]:
        if not self._config.WITHDRAWALS_ENABLED:
            raise Exception("Withdrawals are disabled")

        if not is_address(destination):
            raise ValueError("{} is not valid ETH address".format(destination))

        if currency == 'ETH':
            if amount > self.get_available_eth():
                raise NotEnoughFunds(
                    amount,
                    self.get_available_eth(),
                    currency,
                )
            log.info(
                "Withdrawing %f ETH to %s",
                amount / denoms.ether,
                destination,
            )
            return [self._sci.transfer_eth(destination, amount)]

        if currency == 'GNT':
            if amount > self.get_available_gnt():
                raise NotEnoughFunds(
                    amount,
                    self.get_available_gnt(),
                    currency,
                )
            log.info(
                "Withdrawing %f GNT to %s",
                amount / denoms.ether,
                destination,
            )
            return [self._sci.convert_gntb_to_gnt(destination, amount)]

        raise ValueError('Unknown currency {}'.format(currency))

    def concent_balance(self) -> int:
        return self._sci.get_deposit_value(self._sci.get_eth_address())

    def concent_deposit(self, required: int, expected: int, cb=None) -> None:
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
        gntb_balance = self.get_available_gnt()
        if gntb_balance < required:
            raise NotEnoughFunds(required, gntb_balance, 'GNTB')
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
        if not self._config.FAUCET_ENABLED:
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

    def _refresh_balances(self) -> None:
        now = time.mktime(datetime.today().timetuple())
        addr = self._sci.get_eth_address()

        # Sometimes web3 may throw but it's fine here, we'll just update the
        # balances next time
        try:
            self._eth_balance = self._sci.get_eth_balance(addr)
            self._last_eth_update = now

            self._gnt_balance = self._sci.get_gnt_balance(addr)
            self._gntb_balance = self._sci.get_gntb_balance(addr)
            self._last_gnt_update = now
        except Exception as e:  # pylint: disable=broad-except
            log.warning('Failed to update balances: %r', e)

    def _try_convert_gnt(self) -> None:  # pylint: disable=too-many-branches
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
