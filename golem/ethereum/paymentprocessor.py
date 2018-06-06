import calendar
import logging
import time
from collections import defaultdict
from typing import Dict, List
from threading import Lock

from sortedcontainers import SortedListWithKey
from ethereum.utils import denoms
from pydispatch import dispatcher

import golem_sci
from golem.core.variables import PAYMENT_DEADLINE
from golem.model import db, Payment, PaymentStatus
from golem.utils import encode_hex

log = logging.getLogger("golem.pay")

# We reserve 30 minutes for the payment to go through
PAYMENT_MAX_DELAY = PAYMENT_DEADLINE - 30 * 60


def get_timestamp() -> int:
    """This is platform independent timestamp, needed for payments logic"""
    return calendar.timegm(time.gmtime())


def _make_batch_payments(payments: List[Payment]) -> List[golem_sci.Payment]:
    payees: defaultdict = defaultdict(lambda: 0)
    for p in payments:
        payees[p.payee] += p.value
    res = []
    for payee, amount in payees.items():
        res.append(golem_sci.Payment('0x' + encode_hex(payee), amount))
    return res


# pylint: disable=too-many-instance-attributes
class PaymentProcessor:
    # Minimal number of confirmations before we treat transactions as done
    REQUIRED_CONFIRMATIONS = 6

    CLOSURE_TIME_DELAY = 2
    # Don't try to use more than 75% of block gas limit
    BLOCK_GAS_LIMIT_RATIO = 0.75

    def __init__(self, sci) -> None:
        self.ETH_BATCH_PAYMENT_BASE = \
            sci.GAS_PRICE * sci.GAS_BATCH_PAYMENT_BASE
        self._sci = sci
        self._eth_reserved = 0
        self._gntb_reserved = 0
        self._awaiting = SortedListWithKey(key=lambda p: p.processed_ts)
        self._inprogress: Dict[str, List[Payment]] = {}  # Sent transactions.
        self.load_from_db()

    @property
    def reserved_eth(self) -> int:
        return self._eth_reserved + self.ETH_BATCH_PAYMENT_BASE

    @property
    def reserved_gntb(self) -> int:
        return self._gntb_reserved

    def get_gas_cost_per_payment(self) -> int:
        gas_price = \
            min(self._sci.GAS_PRICE, 2 * self._sci.get_current_gas_price())
        return gas_price * self._sci.GAS_PER_PAYMENT

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

    def add(self, payment):
        if payment.status is not PaymentStatus.awaiting:
            raise RuntimeError(
                "Invalid payment status: {}".format(payment.status))

        log.info("Payment {:.6} to {:.6} ({:.6f})".format(
            payment.subtask,
            encode_hex(payment.payee),
            payment.value / denoms.ether))

        ts = get_timestamp()
        if not payment.processed_ts:
            with Payment._meta.database.transaction():
                payment.processed_ts = ts
                payment.save()

        self._awaiting.add(payment)

        self._gntb_reserved += payment.value
        self._eth_reserved += self.get_gas_cost_per_payment()

        log.info("GNTB reserved %.6f", self._gntb_reserved / denoms.ether)

    def __get_next_batch(self, closure_time: int) -> int:
        gntb_balance = self._sci.get_gntb_balance(self._sci.get_eth_address())
        eth_balance = self._sci.get_eth_balance(self._sci.get_eth_address())
        if not gntb_balance or not eth_balance:
            return 0
        eth_balance = eth_balance - self.ETH_BATCH_PAYMENT_BASE
        ind = 0
        eth_per_payment = self.get_gas_cost_per_payment()
        gas_limit = \
            self._sci.get_latest_block().gas_limit * self.BLOCK_GAS_LIMIT_RATIO
        payees = set()
        for p in self._awaiting:
            if p.processed_ts > closure_time:
                break
            gntb_balance -= p.value
            if gntb_balance < 0:
                break

            payees.add(p.payee)
            if len(payees) * eth_per_payment > eth_balance:
                break
            gas = len(payees) * self._sci.GAS_PER_PAYMENT + \
                self._sci.GAS_BATCH_PAYMENT_BASE
            if gas > gas_limit:
                break

            ind += 1

        # we need to take either all payments with given processed_ts or none
        if ind < len(self._awaiting):
            while ind > 0 and self._awaiting[ind - 1]\
                    .processed_ts == self._awaiting[ind].processed_ts:
                ind -= 1

        return ind

    def sendout(self, acceptable_delay: int = PAYMENT_MAX_DELAY):
        if not self._awaiting:
            return False

        now = get_timestamp()
        deadline = self._awaiting[0].processed_ts + acceptable_delay
        if deadline > now:
            log.info("Next sendout in {} s".format(deadline - now))
            return False

        payments_count = self.__get_next_batch(now - self.CLOSURE_TIME_DELAY)
        if payments_count == 0:
            return False
        payments = self._awaiting[:payments_count]
        del self._awaiting[:payments_count]

        value = sum([p.value for p in payments])
        log.info("Batch payments value: {:.6f}".format(value / denoms.ether))

        closure_time = payments[-1].processed_ts
        try:
            tx_hash = self._sci.batch_transfer(
                _make_batch_payments(payments),
                closure_time,
            )
        except Exception as e:
            log.warning("Exception while sending batch transfer {}".format(e))
            self._awaiting.update(payments)
            return False

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
        # TODO: Maybe we should only monitor the latest block? issue #2414
        self._gntb_reserved -= value
        self._eth_reserved = \
            len(self._awaiting) * self.get_gas_cost_per_payment()
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

    def run(self) -> None:
        if self._sci.is_synchronized():
            self.monitor_progress()
            self.sendout()
