import calendar
import logging
import sys
import time
import requests
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from ethereum.utils import normalize_address, denoms
from pydispatch import dispatcher

from golem.core.service import LoopingCallService
from golem.model import db, Payment, PaymentStatus
from golem.utils import encode_hex

from .gntconverter import GNTConverter

log = logging.getLogger("golem.pay")

DONATE_URL_TEMPLATE = "http://188.165.227.180:4000/donate/{}"


def get_timestamp() -> int:
    """This is platform independent timestamp, needed for payments logic"""
    return calendar.timegm(time.gmtime())


def tETH_faucet_donate(addr):
    addr = normalize_address(addr)
    request = DONATE_URL_TEMPLATE.format(addr.hex())
    response = requests.get(request)
    if response.status_code != 200:
        log.error("tETH Faucet error code {}".format(response.status_code))
        return False
    response = response.json()
    if response['paydate'] == 0:
        log.warning("tETH Faucet warning {}".format(response['message']))
        return False
    # The paydate is not actually very reliable, usually some day in the past.
    paydate = datetime.fromtimestamp(response['paydate'])
    amount = int(response['amount']) / denoms.ether
    log.info("Faucet: {:.6f} ETH on {}".format(amount, paydate))
    return True


class PaymentProcessor(LoopingCallService):
    # Default deadline in seconds for new payments.
    DEFAULT_DEADLINE = 10 * 60

    # Minimal number of confirmations before we treat transactions as done
    REQUIRED_CONFIRMATIONS = 12

    CLOSURE_TIME_DELAY = 10

    def __init__(self,
                 sci,
                 faucet=False) -> None:
        self.ETH_PER_PAYMENT = sci.GAS_PRICE * sci.GAS_PER_PAYMENT
        self.ETH_BATCH_PAYMENT_BASE = \
            sci.GAS_PRICE * sci.GAS_BATCH_PAYMENT_BASE
        self._sci = sci
        self._gnt_converter = GNTConverter(sci)
        self.__eth_balance = None  # type: Optional[int]
        self.__gnt_balance = None  # type: Optional[int]
        self.__gntw_balance = None  # type: Optional[int]
        self.__eth_reserved = 0
        self.__gntw_reserved = 0
        self._awaiting_lock = Lock()
        self._awaiting = []  # type: List[Any] # Awaiting individual payments
        self._inprogress = {}  # type: Dict[Any,Any] # Sent transactions.
        self.__faucet = faucet
        self.deadline = sys.maxsize
        self.load_from_db()
        self._last_gnt_update = None
        self._last_eth_update = None
        super().__init__(13)

    def balance_known(self):
        return self.__gnt_balance is not None and \
            self.__gntw_balance is not None and \
            self.__eth_balance is not None

    def eth_balance(self, refresh=False):
        # FIXME: The balance must be actively monitored!
        if self.__eth_balance is None or refresh:
            balance = self._sci.get_eth_balance(self._sci.get_eth_address())
            if balance is not None:
                self.__eth_balance = balance
                log.info("ETH: {}".format(self.__eth_balance / denoms.ether))
                self._last_eth_update = time.mktime(
                    datetime.today().timetuple())
            else:
                log.warning("Failed to retrieve ETH balance")
        return (self.__eth_balance, self._last_eth_update)

    def gnt_balance(self, refresh=False):
        if self.__gnt_balance is None or self.__gntw_balance is None or refresh:
            gnt_balance = self._sci.get_gnt_balance(
                self._sci.get_eth_address())
            if gnt_balance is not None:
                self.__gnt_balance = gnt_balance
            else:
                log.warning("Failed to retrieve GNT balance")

            gntw_balance = self._sci.get_gntw_balance(
                self._sci.get_eth_address())
            if gntw_balance is not None:
                self.__gntw_balance = gntw_balance
            else:
                log.warning("Failed to retrieve GNTW balance")

            if self.__gnt_balance is not None and \
               self.__gntw_balance is not None:
                log.info(
                    "GNT: %r GNTW: %r",
                    self.__gnt_balance / denoms.ether,
                    self.__gntw_balance / denoms.ether,
                )
                self._last_gnt_update = time.mktime(
                    datetime.today().timetuple())

        return (self.__gnt_balance + self.__gntw_balance,
                self._last_gnt_update)

    def _eth_reserved(self):
        return self.__eth_reserved + self.ETH_BATCH_PAYMENT_BASE

    def _eth_available(self):
        """ Returns available ETH balance for new payments fees."""
        eth_balance, _ = self.eth_balance()
        return eth_balance - self._eth_reserved()

    def _gnt_reserved(self):
        return self.__gntw_reserved

    def _gnt_available(self):
        gnt_balance, _ = self.gnt_balance()
        return gnt_balance - self.__gntw_reserved

    def load_from_db(self):
        with db.atomic():
            for sent_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.sent):
                transaction_hash = '0x' + sent_payment.details.tx
                if transaction_hash not in self._inprogress:
                    self._inprogress[transaction_hash] = []
                self._inprogress[transaction_hash].append(sent_payment)
            for awaiting_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.awaiting):
                self.add(awaiting_payment)

    def add(self, payment, deadline=DEFAULT_DEADLINE):
        if payment.status is not PaymentStatus.awaiting:
            raise RuntimeError(
                "Invalid payment status: {}".format(payment.status))

        log.info("Payment {:.6} to {:.6} ({:.6f})".format(
            payment.subtask,
            encode_hex(payment.payee),
            payment.value / denoms.ether))

        with self._awaiting_lock:
            ts = get_timestamp()
            if not payment.processed_ts:
                with Payment._meta.database.transaction():
                    payment.processed_ts = ts
                    payment.save()

            self._awaiting.append(payment)
            # TODO: Optimize by checking the time once per service update.
            self.deadline = min(self.deadline, ts + deadline)

        self.__gntw_reserved += payment.value
        self.__eth_reserved += self.ETH_PER_PAYMENT

        log.info("GNT: available {:.6f}, reserved {:.6f}".format(
            self._gnt_available() / denoms.ether,
            self.__gntw_reserved / denoms.ether))

    def __get_next_batch(
            self,
            payments: List[Payment],
            closure_time: int) -> Tuple[List[Payment], List[Payment]]:
        payments.sort(key=lambda p: p.processed_ts)
        gntw_balance = self.__gntw_balance
        eth_balance, _ = self.eth_balance()
        eth_balance = eth_balance - self.ETH_BATCH_PAYMENT_BASE
        ind = 0
        for p in payments:
            if p.processed_ts > closure_time:
                break
            gntw_balance -= p.value
            eth_balance -= self.ETH_PER_PAYMENT
            if gntw_balance < 0 or eth_balance < 0:
                break
            ind += 1

        # we need to take either all payments with given processed_ts or none
        if ind < len(payments):
            while ind > 0 and payments[ind - 1]\
                    .processed_ts == payments[ind].processed_ts:
                ind -= 1

        return payments[:ind], payments[ind:]

    def sendout(self):
        with self._awaiting_lock:
            if not self._awaiting:
                return False

            now = get_timestamp()
            if self.deadline > now:
                log.info("Next sendout in {} s".format(self.deadline - now))
                return False

            if self._gnt_converter.is_converting():
                log.info('Waiting for GNT-GNTW conversion')
                return False

            closure_time = now - self.CLOSURE_TIME_DELAY

            payments, rest = self.__get_next_batch(
                self._awaiting.copy(),
                closure_time)
            if rest and self.__gnt_balance:
                log.info(
                    'Will convert %r GNT before sending out payments',
                    self.__gnt_balance / denoms.ether,
                )
                self._gnt_converter.convert(self.__gnt_balance)
                return False
            if not payments:
                return False
            self._awaiting = rest

        value = sum([p.value for p in payments])
        log.info("Batch payments value: {:.6f}".format(value / denoms.ether))

        tx_hash = self._sci.batch_transfer(payments, closure_time)
        with Payment._meta.database.transaction():
            for payment in payments:
                payment.status = PaymentStatus.sent
                payment.details.tx = tx_hash[2:]
                payment.save()
                log.debug("- {} send to {} ({:.6f})".format(
                    payment.subtask,
                    encode_hex(payment.payee),
                    payment.value / denoms.ether))

            self._inprogress[tx_hash] = payments

        # Remove from reserved, because we monitor the pending block.
        # TODO: Maybe we should only monitor the latest block?
        self.__gntw_reserved -= value
        self.__eth_reserved -= len(payments) * self.ETH_PER_PAYMENT
        return True

    def monitor_progress(self):
        if not self._inprogress:
            return

        confirmed = []
        failed = {}
        current_block = self._sci.get_block_number()

        for hstr, payments in self._inprogress.items():
            log.info("Checking {:.6} tx [{}]".format(hstr, len(payments)))
            receipt = self._sci.get_transaction_receipt(hstr)
            if not receipt:
                continue

            block_hash = receipt.block_hash[2:]

            block_number = receipt.block_number
            if current_block - block_number < self.REQUIRED_CONFIRMATIONS:
                continue

            # if the transaction failed for whatever reason we need to retry
            if not receipt.status:
                with Payment._meta.database.transaction():
                    for p in payments:
                        p.status = PaymentStatus.awaiting
                        p.save()
                failed[hstr] = payments
                log.warning("Failed transaction: %r", receipt)
                continue

            gas_used = receipt.gas_used
            total_fee = gas_used * self._sci.GAS_PRICE
            fee = total_fee // len(payments)
            log.info("Confirmed {:.6}: block {} ({}), gas {}, fee {}"
                     .format(hstr, block_hash, block_number, gas_used, fee))
            with Payment._meta.database.transaction():
                for p in payments:
                    p.status = PaymentStatus.confirmed
                    p.details.block_number = block_number
                    p.details.block_hash = block_hash
                    p.details.fee = fee
                    p.save()
                    dispatcher.send(
                        signal='golem.monitor',
                        event='payment',
                        addr=encode_hex(p.payee),
                        value=p.value
                    )
                    log.debug(
                        "- %.6f confirmed fee %.6f",
                        p.subtask,
                        fee / denoms.ether
                    )
            confirmed.append(hstr)

        for h in confirmed:
            del self._inprogress[h]

        for h, payments in failed.items():
            del self._inprogress[h]
            for p in payments:
                self.add(p)

    def get_ether_from_faucet(self):
        eth_balance, _ = self.eth_balance(True)
        if eth_balance is None:
            return False

        if self.__faucet and eth_balance < 0.01 * denoms.ether:
            log.info("Requesting tETH")
            tETH_faucet_donate(self._sci.get_eth_address())
            return False
        return True

    def get_gnt_from_faucet(self):
        gnt_balance, _ = self.gnt_balance(True)
        if gnt_balance is None:
            return False

        if self.__faucet and gnt_balance < 100 * denoms.ether:
            log.info("Requesting GNT from faucet")
            self._sci.request_gnt_from_faucet()
            return False
        return True

    def _send_balance_snapshot(self):
        dispatcher.send(
            signal='golem.monitor',
            event='balance_snapshot',
            eth_balance=self.__eth_balance,
            gnt_balance=self.__gnt_balance,
            gntw_balance=self.__gntw_balance
        )

    def _run(self):
        if self._sci.is_synchronized() and \
                self.get_ether_from_faucet() and \
                self.get_gnt_from_faucet():
            self.monitor_progress()
            self.sendout()
            self._send_balance_snapshot()
