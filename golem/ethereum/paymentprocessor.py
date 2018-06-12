import calendar
import logging
import time
from collections import defaultdict
from typing import Dict, List
from threading import Lock

from sortedcontainers import SortedListWithKey
from ethereum.utils import denoms
from pydispatch import dispatcher
from twisted.internet import threads

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


class PaymentProcessor:
    CLOSURE_TIME_DELAY = 2
    # Don't try to use more than 75% of block gas limit
    BLOCK_GAS_LIMIT_RATIO = 0.75

    def __init__(self, sci) -> None:
        self.ETH_BATCH_PAYMENT_BASE = \
            sci.GAS_PRICE * sci.GAS_BATCH_PAYMENT_BASE
        self._sci = sci
        self._gntb_reserved = 0
        self._awaiting = SortedListWithKey(key=lambda p: p.processed_ts)
        self.load_from_db()

    @property
    def reserved_eth(self) -> int:
        if not self._awaiting:
            return 0
        return self.ETH_BATCH_PAYMENT_BASE + \
            len(self._awaiting) * self.get_gas_cost_per_payment()

    @property
    def reserved_gntb(self) -> int:
        return self._gntb_reserved

    def get_gas_cost_per_payment(self) -> int:
        gas_price = \
            min(self._sci.GAS_PRICE, 2 * self._sci.get_current_gas_price())
        return gas_price * self._sci.GAS_PER_PAYMENT

    def load_from_db(self):
        with db.atomic():
            sent = {}
            for sent_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.sent):
                tx_hash = '0x' + sent_payment.details.tx
                if tx_hash not in sent:
                    sent[tx_hash] = []
                sent[tx_hash].append(sent_payment)
                self._gntb_reserved += sent_payment.value
            for tx_hash, payments in sent.items():
                self._sci.on_transaction_confirmed(
                    tx_hash,
                    lambda r: threads.deferToThread(
                        self._on_batch_confirmed, payments.copy(), r),
                )

            for awaiting_payment in Payment \
                    .select() \
                    .where(Payment.status == PaymentStatus.awaiting):
                self.add(awaiting_payment)

    def _on_batch_confirmed(self, payments: List[Payment], receipt) -> None:
        if not receipt.status:
            log.critical("Failed batch transfer: %s", receipt)
            for p in payments:
                p.status = PaymentStatus.awaiting  # type: ignore
                p.save()
                self._gntb_reserved -= p.value
                self.add(p)
            return

        # TODO: Use the actual gas price of the transaction
        total_fee = receipt.gas_used * self._sci.GAS_PRICE
        fee = total_fee // len(payments)
        log.info(
            "Batch transfer confirmed %s average gas fee per subtask %f",
            receipt,
            fee / denoms.ether,
        )
        for p in payments:
            p.status = PaymentStatus.confirmed  # type: ignore
            p.details.block_number = receipt.block_number
            p.details.block_hash = receipt.block_hash[2:]
            p.details.fee = fee
            p.save()
            self._gntb_reserved -= p.value
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

            self._sci.on_transaction_confirmed(
                tx_hash,
                lambda r: threads.deferToThread(
                    self._on_batch_confirmed, payments, r)
            )

        return True
