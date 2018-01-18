import calendar
import logging
import sys
import time
import requests
from datetime import datetime
from threading import Lock
from typing import Any, List

from ethereum import utils, keys
from ethereum.utils import normalize_address, denoms
from pydispatch import dispatcher

from golem.core.service import LoopingCallService
from golem.model import db, Payment, PaymentStatus
from golem.utils import decode_hex, encode_hex

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
                 privkey,
                 sci,
                 faucet=False) -> None:
        self.ETH_PER_PAYMENT = sci.GAS_PRICE * sci.GAS_PER_PAYMENT
        self.ETH_BATCH_PAYMENT_BASE = \
            sci.GAS_PRICE * sci.GAS_BATCH_PAYMENT_BASE
        self._sci = sci
        self.__privkey = privkey
        self.__eth_balance = None
        self.__gnt_balance = None
        self.__eth_reserved = 0
        self.__gnt_reserved = 0
        self._awaiting_lock = Lock()
        self._awaiting = []  # type: List[Any] # Awaiting individual payments
        self._inprogress = {}  # type: Dict[Any,Any] # Sent transactions.
        self.__faucet = faucet
        self.deadline = sys.maxsize
        self.load_from_db()
        super().__init__(13)

    def eth_address(self, zpad=True):
        raw = keys.privtoaddr(self.__privkey)
        # TODO: Hack RPC client to allow using raw address.
        if zpad:
            raw = utils.zpad(raw, 32)
        return '0x' + encode_hex(raw)

    def balance_known(self):
        return self.__gnt_balance is not None and self.__eth_balance is not None

    def eth_balance(self, refresh=False):
        # FIXME: The balance must be actively monitored!
        if self.__eth_balance is None or refresh:
            addr = self.eth_address(zpad=False)
            balance = self._sci.get_eth_balance(addr)
            if balance is not None:
                self.__eth_balance = balance
                log.info("ETH: {}".format(self.__eth_balance / denoms.ether))
            else:
                log.warning("Failed to retrieve ETH balance")
        return self.__eth_balance

    def gnt_balance(self, refresh=False):
        if self.__gnt_balance is None or refresh:
            gnt_balance = self._sci.get_gnt_balance(
                self.eth_address(zpad=False))
            gntw_balance = self._sci.get_gntw_balance(
                self.eth_address(zpad=False))
            if gnt_balance is not None and gntw_balance is not None:
                log.info("GNT: {} GNTW: {}".format(
                    gnt_balance / denoms.ether, gntw_balance / denoms.ether))
                self.__gnt_balance = gnt_balance + gntw_balance
            else:
                log.warning("Failed to retrieve GNT/GNTW balance")
        return self.__gnt_balance

    def _eth_reserved(self):
        return self.__eth_reserved + self.ETH_BATCH_PAYMENT_BASE

    def _eth_available(self):
        """ Returns available ETH balance for new payments fees."""
        return self.eth_balance() - self._eth_reserved()

    def _gnt_reserved(self):
        return self.__gnt_reserved

    def _gnt_available(self):
        return self.gnt_balance() - self.__gnt_reserved

    def load_from_db(self):
        with db.atomic():
            for sent_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.sent):
                transaction_hash = decode_hex(sent_payment.details.tx)
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

        self.__gnt_reserved += payment.value
        self.__eth_reserved += self.ETH_PER_PAYMENT

        log.info("GNT: available {:.6f}, reserved {:.6f}".format(
            self._gnt_available() / denoms.ether,
            self.__gnt_reserved / denoms.ether))

    def __get_next_batch(self,
                         payments: List[Payment],
                         closure_time: int) -> (List[Payment], List[Payment]):
        payments.sort(key=lambda p: p.processed_ts)
        gnt_balance = self.gnt_balance()
        eth_balance = self.eth_balance() - self.ETH_BATCH_PAYMENT_BASE
        ind = 0
        for p in payments:
            if p.processed_ts > closure_time:
                break
            gnt_balance -= p.value
            eth_balance -= self.ETH_PER_PAYMENT
            if gnt_balance < 0 or eth_balance < 0:
                break
            ind += 1

        # we need to take either all payments with given processed_ts or none
        if ind < len(payments):
            while ind > 0 and payments[ind-1].processed_ts == payments[ind].processed_ts:  # noqa
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

            closure_time = now - self.CLOSURE_TIME_DELAY

            payments, rest = self.__get_next_batch(
                self._awaiting.copy(),
                closure_time)
            if not payments:
                return False
            self._awaiting = rest

        tx = self._sci.prepare_batch_transfer(
            self.__privkey,
            payments,
            closure_time)
        if not tx:
            with self._awaiting_lock:
                payments.extend(self._awaiting)
                self._awaiting = payments
            return False

        tx.sign(self.__privkey)
        value = sum([p.value for p in payments])
        h = tx.hash
        log.info("Batch payments: {:.6}, value: {:.6f}"
                 .format(encode_hex(h), value / denoms.ether))

        # If awaiting payments are not empty it means a new payment has been
        # added between clearing the awaiting list and here. In that case
        # we shouldn't update the deadline to sys.maxsize.
        with self._awaiting_lock:
            if not self._awaiting:
                self.deadline = sys.maxsize

        # Firstly write transaction hash to database. We need the hash to be
        # remembered before sending the transaction to the Ethereum node in
        # case communication with the node is interrupted and it will be not
        # known if the transaction has been sent or not.
        with Payment._meta.database.transaction():
            for payment in payments:
                payment.status = PaymentStatus.sent
                payment.details.tx = encode_hex(h)
                payment.save()
                log.debug("- {} send to {} ({:.6f})".format(
                    payment.subtask,
                    encode_hex(payment.payee),
                    payment.value / denoms.ether))

            tx_hash = self._sci.send_transaction(tx)
            tx_hex = decode_hex(tx_hash)
            if tx_hex != h:  # FIXME: Improve Client.
                raise RuntimeError("Incorrect tx hash: {}, should be: {}"
                                   .format(tx_hex, h))

            self._inprogress[h] = payments

        # Remove from reserved, because we monitor the pending block.
        # TODO: Maybe we should only monitor the latest block?
        self.__gnt_reserved -= value
        self.__eth_reserved -= len(payments) * self.ETH_PER_PAYMENT
        return True

    def monitor_progress(self):
        if not self._inprogress:
            return

        confirmed = []
        failed = {}
        current_block = self._sci.get_block_number()

        for h, payments in self._inprogress.items():
            hstr = '0x' + encode_hex(h)
            log.info("Checking {:.6} tx [{}]".format(hstr, len(payments)))
            receipt = self._sci.get_transaction_receipt(hstr)
            if not receipt:
                continue

            block_hash = receipt['blockHash'][2:]
            if len(block_hash) != 64:
                raise ValueError(
                    "block hash length should be 64, but is: {}".format(
                        len(block_hash)))

            block_number = receipt['blockNumber']
            if current_block - block_number < self.REQUIRED_CONFIRMATIONS:
                continue

            # if the transaction failed for whatever reason we need to retry
            if receipt['status'] != '0x1':
                with Payment._meta.database.transaction():
                    for p in payments:
                        p.status = PaymentStatus.awaiting
                        p.save()
                failed[h] = payments
                log.warning("Failed transaction: {}".format(receipt))
                continue

            gas_used = receipt['gasUsed']
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
            confirmed.append(h)

        for h in confirmed:
            del self._inprogress[h]

        for h, payments in failed.items():
            del self._inprogress[h]
            for p in payments:
                self.add(p)

    def get_ether_from_faucet(self):
        if self.__faucet and self.eth_balance(True) < 0.01 * denoms.ether:
            log.info("Requesting tETH")
            addr = keys.privtoaddr(self.__privkey)
            tETH_faucet_donate(addr)
            return False
        return True

    def get_gnt_from_faucet(self):
        if self.__faucet and self.gnt_balance(True) < 100 * denoms.ether:
            log.info("Requesting GNT from faucet")
            self._sci.request_gnt_from_faucet(self.__privkey)
            return False
        return True

    def _run(self):
        if self._sci.is_synchronized() and \
                self.get_ether_from_faucet() and \
                self.get_gnt_from_faucet():
            self.monitor_progress()
            self.sendout()
