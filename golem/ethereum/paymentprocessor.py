import calendar
import datetime
import logging
import time

from collections import defaultdict
from typing import List

from pydispatch import dispatcher
from sortedcontainers import SortedListWithKey
from eth_utils import decode_hex, encode_hex
from ethereum.utils import denoms
from twisted.internet import threads

import golem_sci

from golem.core.variables import PAYMENT_DEADLINE
from golem.model import Payment, PaymentStatus

log = logging.getLogger(__name__)

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
        res.append(golem_sci.Payment(encode_hex(payee), amount))
    return res


class PaymentProcessor:
    CLOSURE_TIME_DELAY = 2
    # Don't try to use more than 75% of block gas limit
    BLOCK_GAS_LIMIT_RATIO = 0.75

    def __init__(self, sci) -> None:
        self._sci = sci
        self._gntb_reserved = 0
        self._awaiting = SortedListWithKey(key=lambda p: p.processed_ts)
        self.load_from_db()
        self.last_print_time = 0

    @property
    def recipients_count(self) -> int:
        return len(self._awaiting)

    @property
    def reserved_gntb(self) -> int:
        return self._gntb_reserved

    def load_from_db(self):
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
                lambda r, p=payments: threads.deferToThread(
                    self._on_batch_confirmed, p, r),
            )

        for awaiting_payment in Payment \
                .select() \
                .where(
                        Payment.status.in_([
                            PaymentStatus.awaiting,
                            PaymentStatus.overdue,
                        ]),
                ):
            log.info(
                "Restoring awaiting payment for subtask %s to %s of %.3f GNTB",
                awaiting_payment.subtask,
                encode_hex(awaiting_payment.payee),
                awaiting_payment.value / denoms.ether,
            )
            self._awaiting.add(awaiting_payment)
            self._gntb_reserved += awaiting_payment.value

    def _on_batch_confirmed(self, payments: List[Payment], receipt) -> None:
        if not receipt.status:
            log.critical("Failed batch transfer: %s", receipt)
            for p in payments:
                p.status = PaymentStatus.awaiting  # type: ignore
                p.save()
                self._awaiting.add(p)
            return

        block = self._sci.get_block_by_number(receipt.block_number)
        gas_price = self._sci.get_transaction_gas_price(receipt.tx_hash)
        total_fee = receipt.gas_used * gas_price
        fee = total_fee // len(payments)
        log.info(
            "Batch transfer confirmed %s average gas fee per subtask %.8f ETH",
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
            self._payment_confirmed(p, block.timestamp)

    @staticmethod
    def _payment_confirmed(payment: Payment, timestamp: int) -> None:
        log.debug(
            "- %s confirmed fee: %.18f ETH",
            payment.subtask,
            payment.details.fee / denoms.ether
        )

        reference_date = datetime.datetime.fromtimestamp(timestamp)
        delay = (reference_date - payment.created_date).seconds

        dispatcher.send(
            signal="golem.payment",
            event="confirmed",
            subtask_id=payment.subtask,
            payee=payment.payee,
            delay=delay,
        )

    def add(self, subtask_id: str, eth_addr: str, value: int) -> Payment:
        log.info(
            "Adding payment for %s to %s (%.3f GNTB)",
            subtask_id,
            eth_addr,
            value / denoms.ether,
        )
        payment = Payment.create(
            subtask=subtask_id,
            payee=decode_hex(eth_addr),
            value=value,
            processed_ts=get_timestamp(),
        )

        self._awaiting.add(payment)
        self._gntb_reserved += value

        log.info("Reserved %.3f GNTB", self._gntb_reserved / denoms.ether)
        return payment.processed_ts

    def __get_next_batch(self, closure_time: int) -> int:
        gntb_balance = self._sci.get_gntb_balance(self._sci.get_eth_address())
        eth_balance = self._sci.get_eth_balance(self._sci.get_eth_address())
        gas_price = self._sci.get_current_gas_price()

        ind = 0
        gas_limit = \
            self._sci.get_latest_block().gas_limit * self.BLOCK_GAS_LIMIT_RATIO
        payees = set()
        for p in self._awaiting:
            if p.processed_ts > closure_time:
                break
            gntb_balance -= p.value
            if gntb_balance < 0:
                log.debug(
                    'Insufficient GNTB balance.'
                    ' value=%(value).18f, subtask_id=%(subtask)s',
                    {
                        'value': p.value / denoms.ether,
                        'subtask': p.subtask,
                    },
                )
                break

            payees.add(p.payee)
            gas = len(payees) * self._sci.GAS_PER_PAYMENT + \
                self._sci.GAS_BATCH_PAYMENT_BASE
            if gas > gas_limit:
                break
            gas_cost = gas * gas_price
            if gas_cost > eth_balance:
                log.debug(
                    'Not enough ETH to pay gas for transaction.'
                    ' gas_cost=%(gas_cost).18f, subtask_id=%(subtask)s',
                    {
                        'gas_cost': gas_cost / denoms.ether,
                        'subtask': p.subtask,
                    },
                )
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
            if now > self.last_print_time + 300:
                log.info("Next sendout at %s",
                         datetime.datetime.fromtimestamp(deadline))
                self.last_print_time = now
            return False

        payments_count = self.__get_next_batch(now - self.CLOSURE_TIME_DELAY)
        if payments_count == 0:
            return False
        payments = self._awaiting[:payments_count]

        value = sum([p.value for p in payments])
        log.info("Batch payments value: %.3f GNTB", value / denoms.ether)

        closure_time = payments[-1].processed_ts
        tx_hash = self._sci.batch_transfer(
            _make_batch_payments(payments),
            closure_time,
        )
        del self._awaiting[:payments_count]

        for payment in payments:
            payment.status = PaymentStatus.sent
            payment.details.tx = tx_hash[2:]
            payment.save()
            log.debug("- {} send to {} ({:.18f} GNTB)".format(
                payment.subtask,
                encode_hex(payment.payee),
                payment.value / denoms.ether))

        self._sci.on_transaction_confirmed(
            tx_hash,
            lambda r: threads.deferToThread(
                self._on_batch_confirmed, payments, r)
        )

        return True

    def update_overdue(self) -> None:
        """Sets overdue status for awaiting payments"""

        processed_ts_deadline = int(time.time()) - PAYMENT_DEADLINE
        counter = 0
        for payment in self._awaiting:
            if payment.processed_ts >= processed_ts_deadline:
                # All subsequent payments won't be overdue
                # because list is sorted.
                break
            if payment.status is PaymentStatus.overdue:
                continue
            payment.status = PaymentStatus.overdue
            payment.save()
            log.debug("Marked as overdue. payment=%r", payment)
            counter += 1
        if counter:
            log.info("Marked %d payments as overdue.", counter)
