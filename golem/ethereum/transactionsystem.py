import json
import logging
import os
import random
import time
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, Optional, List

from ethereum.utils import denoms
from eth_keyfile import create_keyfile_json, extract_key_from_keyfile
from eth_utils import decode_hex, is_address
from golem_messages.utils import bytes32_to_uuid
from golem_sci import new_sci, SmartContractsInterface, JsonTransactionsStorage
from twisted.internet.defer import Deferred
import requests

from golem.core.service import LoopingCallService
from golem.ethereum.node import NodeProcess
from golem.ethereum.paymentprocessor import PaymentProcessor
from golem.ethereum.exceptions import NotEnoughFunds
from golem.ethereum.incomeskeeper import IncomesKeeper
from golem.ethereum.paymentskeeper import PaymentsKeeper
from golem.model import GenericKeyValue, Payment, Income
from golem.utils import privkeytoaddr


log = logging.getLogger(__name__)


class ConversionStatus(Enum):
    NONE = 0
    OPENING_GATE = 1
    TRANSFERRING = 2
    UNFINISHED = 3


# pylint:disable=too-many-instance-attributes
class TransactionSystem(LoopingCallService):
    """ Transaction system connected with Ethereum """

    TX_FILENAME: ClassVar[str] = 'transactions.json'
    KEYSTORE_FILENAME: ClassVar[str] = 'wallet.json'

    BLOCK_NUMBER_DB_KEY: ClassVar[str] = 'ets_subscriptions_block_number'

    LOOP_INTERVAL: ClassVar[int] = 13

    def __init__(self, datadir: Path, config) -> None:
        super().__init__(self.LOOP_INTERVAL)
        datadir.mkdir(exist_ok=True)

        self._datadir = datadir
        self._config = config
        self._privkey = b''

        node_list = config.NODE_LIST.copy()
        random.shuffle(node_list)
        node_list += config.FALLBACK_NODE_LIST
        self._node = NodeProcess(node_list)
        self._sci: Optional[SmartContractsInterface] = None

        self._payments_keeper = PaymentsKeeper()
        self._incomes_keeper = IncomesKeeper()
        self._payment_processor: Optional[PaymentProcessor] = None

        self._gnt_faucet_requested = False
        self._gnt_conversion_status = ConversionStatus.NONE

        self._eth_balance: int = 0
        self._gnt_balance: int = 0
        self._gntb_balance: int = 0
        self._last_eth_update: Optional[float] = None
        self._last_gnt_update: Optional[float] = None
        self._payments_locked: int = 0
        self._gntb_locked: int = 0
        # Amortized gas cost per payment used when dealing with locks
        self._eth_per_payment: int = 0

    def backwards_compatibility_tx_storage(self, old_datadir: Path) -> None:
        if self.running:
            raise Exception(
                "Service already started, can't do backwards compatibility")
        # Filename is the same as TX_FILENAME, but the constant shouldn't be
        # used here as if it ever changes this value below should stay the same.
        old_storage_path = old_datadir / 'transactions.json'
        if not old_storage_path.exists():
            return
        log.info(
            "Initializing transaction storage from old path: %s",
            old_storage_path,
        )
        new_storage_path = self._datadir / self.TX_FILENAME
        if new_storage_path.exists():
            raise Exception("Storage already exists, can't override")
        with open(old_storage_path, 'r') as f:
            json_content = json.load(f)
        with open(new_storage_path, 'w') as f:
            json.dump(json_content, f)
        os.remove(old_storage_path)

    def backwards_compatibility_privkey(
            self,
            privkey: bytes,
            password: str) -> None:
        keystore_path = self._datadir / self.KEYSTORE_FILENAME

        # Sanity check that this is in fact still the same key
        if keystore_path.exists():
            self.set_password(password)
            try:
                if privkey != self._privkey:
                    raise Exception("Private key is not backward compatible")
            finally:
                self._privkey = b''
            return

        log.info("Initializing keystore with backward compatible value")
        keystore = create_keyfile_json(
            privkey,
            password.encode('utf-8'),
            iterations=1024,
        )
        with open(keystore_path, 'w') as f:
            json.dump(keystore, f)

    def _init(self) -> None:
        if len(self._privkey) != 32:
            raise Exception(
                "Invalid private key. Did you forget to set password?")
        eth_addr = privkeytoaddr(self._privkey)
        log.info("Node Ethereum address: %s", eth_addr)

        self._node.start()

        self._sci = new_sci(
            self._node.web3,
            eth_addr,
            self._config.CHAIN,
            JsonTransactionsStorage(self._datadir / self.TX_FILENAME),
            lambda tx: tx.sign(self._privkey),
        )

        gate_address = self._sci.get_gate_address()
        if gate_address is not None:
            if self._sci.get_gnt_balance(gate_address):
                self._gnt_conversion_status = ConversionStatus.UNFINISHED

        self._payment_processor = PaymentProcessor(self._sci)
        self._eth_per_payment = self._current_eth_per_payment()
        recipients_count = self._payment_processor.recipients_count
        if recipients_count > 0:
            required_eth = recipients_count * self._eth_per_payment
            if required_eth > self._eth_balance:
                self._eth_per_payment = self._eth_balance // recipients_count

        self._subscribe_to_events()

        self._refresh_balances()
        log.info(
            "Initial balances: %f GNTB, %f GNT, %f ETH",
            self._gntb_balance / denoms.ether,
            self._gnt_balance / denoms.ether,
            self._eth_balance / denoms.ether,
        )

    def start(self, now: bool = True) -> None:
        self._init()
        super().start(now)

    def set_password(self, password: str) -> None:
        keystore_path = self._datadir / self.KEYSTORE_FILENAME
        if keystore_path.exists():
            self._privkey = extract_key_from_keyfile(
                str(keystore_path),
                password.encode('utf-8'),
            )
        else:
            log.info("Generating new Ethereum private key")
            self._privkey = os.urandom(32)
            keystore = create_keyfile_json(
                self._privkey,
                password.encode('utf-8'),
                iterations=1024,
            )
            with open(keystore_path, 'w') as f:
                json.dump(keystore, f)

    def _subscribe_to_events(self) -> None:
        if not self._sci:
            raise Exception('Start was not called')
        values = GenericKeyValue.select().where(
            GenericKeyValue.key == self.BLOCK_NUMBER_DB_KEY)
        from_block = int(values.get().value) if values.count() == 1 else 0

        ik = self._incomes_keeper
        self._sci.subscribe_to_batch_transfers(
            None,
            self._sci.get_eth_address(),
            from_block,
            lambda event: ik.received_batch_transfer(
                event.tx_hash,
                event.sender,
                event.amount,
                event.closure_time,
            )
        )

        # Temporary try-catch block, until GNTDeposit is deployed on mainnet.
        # Remove it after that.
        try:
            self._sci.subscribe_to_forced_subtask_payments(
                None,
                self._sci.get_eth_address(),
                from_block,
                lambda event: ik.received_forced_subtask_payment(
                    event.tx_hash,
                    event.requestor,
                    str(bytes32_to_uuid(event.subtask_id)),
                    event.amount,
                )
            )
            self._sci.subscribe_to_forced_payments(
                requestor_address=None,
                provider_address=self._sci.get_eth_address(),
                from_block=from_block,
                cb=lambda event: ik.received_forced_payment(
                    tx_hash=event.tx_hash,
                    sender=event.requestor,
                    amount=event.amount,
                    closure_time=event.closure_time,
                ),
            )
        except AttributeError as e:
            log.info("Can't use GNTDeposit on mainnet yet: %r", e)

    def _save_subscription_block_number(self) -> None:
        if not self._sci:
            raise Exception('Start was not called')
        block_number = self._sci.get_block_number() - self._sci.REQUIRED_CONFS
        kv, _ = GenericKeyValue.get_or_create(key=self.BLOCK_NUMBER_DB_KEY)
        kv.value = block_number - 1
        kv.save()

    def stop(self):
        self._payment_processor.sendout(0)
        self._save_subscription_block_number()
        self._sci.stop()
        super().stop()

    def add_payment_info(
            self,
            subtask_id: str,
            value: int,
            eth_address: str) -> int:
        if not self._payment_processor:
            raise Exception('Start was not called')
        payee = decode_hex(eth_address)
        if len(payee) != 20:
            raise ValueError(
                "Incorrect 'payee' length: {}. Should be 20".format(len(payee)))
        payment = Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value,
        )
        return self._payment_processor.add(payment)

    def get_payment_address(self):
        """ Human readable Ethereum address for incoming payments."""
        if not self._sci:
            raise Exception('Start was not called')
        return self._sci.get_eth_address()

    def get_payments_list(self):
        """ Return list of all planned and made payments
        :return list: list of dictionaries describing payments
        """
        return self._payments_keeper.get_list_of_all_payments()

    def get_subtasks_payments(
            self,
            subtask_ids: Iterable[str]) -> List[Payment]:
        return self._payments_keeper.get_subtasks_payments(subtask_ids)

    def get_incomes_list(self):
        """ Return list of all expected and received incomes
        :return list: list of dictionaries describing incomes
        """
        return self._incomes_keeper.get_list_of_all_incomes()

    def get_available_eth(self) -> int:
        return self._eth_balance - self.get_locked_eth()

    def get_locked_eth(self) -> int:
        if not self._payment_processor:
            raise Exception('Start was not called')
        payments_num = self._payments_locked + \
            self._payment_processor.recipients_count
        if payments_num == 0:
            return 0
        return payments_num * self._eth_per_payment

    def get_available_gnt(self, account_address: Optional[str] = None) -> int:
        # FIXME Use decorator to DRY #3190
        if not self._sci:
            raise Exception('Start was not called')
        if (account_address is None) \
                or (account_address == self._sci.get_eth_address()):
            return self._gntb_balance - self.get_locked_gnt()
        return self._sci.get_gntb_balance(address=account_address)

    def get_locked_gnt(self) -> int:
        if not self._payment_processor:
            raise Exception('Start was not called')
        return self._gntb_locked + self._payment_processor.reserved_gntb

    def get_balance(self) -> Dict[str, Any]:
        if not self._sci:
            raise Exception('Start was not called')
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
        if not self._payment_processor:
            raise Exception('Start was not called')
        gnt = price * num
        if gnt > self.get_available_gnt():
            raise NotEnoughFunds(gnt, self.get_available_gnt(), 'GNT')

        eth = self.eth_for_batch_payment(num)
        eth_available = self.get_available_eth()
        if eth > eth_available:
            raise NotEnoughFunds(eth, eth_available, 'ETH')

        log.info(
            "Locking %f GNT and ETH for %d payments",
            gnt / denoms.ether,
            num,
        )
        locked_eth = self.get_locked_eth()
        self._gntb_locked += gnt
        self._payments_locked += num
        self._eth_per_payment = (eth + locked_eth) // \
            (self._payments_locked + self._payment_processor.recipients_count)

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

    def expect_income(
            self,
            sender_node: str,
            subtask_id: str,
            payer_address: str,
            value: int) -> Income:
        return self._incomes_keeper.expect(
            sender_node,
            subtask_id,
            payer_address,
            value,
        )

    def reject_income(self, sender_node: str, subtask_id: str) -> None:
        self._incomes_keeper.reject(sender_node, subtask_id)

    def accept_income(
            self,
            sender_node: str,
            subtask_id: str,
            accepted_ts: int) -> None:
        self._incomes_keeper.update_awaiting(
            sender_node,
            subtask_id,
            accepted_ts,
        )

    def settle_income(
            self,
            sender_node: str,
            subtask_id: str,
            settled_ts: int) -> None:
        self._incomes_keeper.settled(sender_node, subtask_id, settled_ts)

    def eth_for_batch_payment(self, num_payments: int) -> int:
        if not self._payment_processor:
            raise Exception('Start was not called')
        num_payments += self._payments_locked + \
            self._payment_processor.recipients_count
        required = self._current_eth_per_payment() * num_payments + \
            self._eth_base_for_batch_payment()
        return required - self.get_locked_eth()

    def _eth_base_for_batch_payment(self) -> int:
        if not self._sci:
            raise Exception('Start was not called')
        return self._sci.GAS_BATCH_PAYMENT_BASE * self._sci.GAS_PRICE

    def _current_eth_per_payment(self) -> int:
        if not self._sci:
            raise Exception('Start was not called')
        gas_price = \
            min(self._sci.GAS_PRICE, 2 * self._sci.get_current_gas_price())
        return gas_price * self._sci.GAS_PER_PAYMENT

    def get_withdraw_gas_cost(
            self,
            amount: int,
            destination: str,
            currency: str) -> int:
        if not self._sci:
            raise Exception('Start was not called')
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
            currency: str) -> str:
        if not self._sci:
            raise Exception('Start was not called')
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
            return self._sci.transfer_eth(destination, amount)

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
            return self._sci.convert_gntb_to_gnt(destination, amount)

        raise ValueError('Unknown currency {}'.format(currency))

    def concent_balance(self, account_address: Optional[str] = None) -> int:
        if not self._sci:
            raise Exception('Start was not called')
        if account_address is None:
            account_address = self._sci.get_eth_address()
        return self._sci.get_deposit_value(
            account_address=account_address,
        )

    def concent_timelock(self, account_address: Optional[str] = None) -> int:
        # FIXME Use decorator to DRY #3190
        if not self._sci:
            raise Exception('Start was not called')
        if account_address is None:
            account_address = self._sci.get_eth_address()
        return self._sci.get_deposit_locked_until(
            account_address=account_address,
        )

    def concent_deposit(self, required: int, expected: int) -> Deferred:
        if not self._sci:
            raise Exception('Start was not called')
        result = Deferred()
        current = self.concent_balance()
        if current >= required:
            result.callback(None)
            return result
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
                result.errback(Exception(f"Deposit failed. Receipt: {receipt}"))
                return
            result.callback(None)

        self._sci.on_transaction_confirmed(tx_hash, transaction_receipt)
        return result

    def _get_funds_from_faucet(self) -> None:
        if not self._sci:
            raise Exception('Start was not called')
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
        if not self._sci:
            raise Exception('Start was not called')
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
        if not self._sci:
            raise Exception('Start was not called')
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
        if not self._payment_processor:
            raise Exception('Start was not called')
        self._refresh_balances()
        self._get_funds_from_faucet()
        self._try_convert_gnt()
        self._payment_processor.sendout()
        self._incomes_keeper.update_overdue_incomes()


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
