import datetime
import logging
import time

from collections import defaultdict
from typing import List

from ethereum.utils import denoms
from golem_messages.datastructures import tasks as dt_tasks
from pydispatch import dispatcher
from sortedcontainers import SortedListWithKey
from twisted.internet import threads

import golem_sci

from golem import model
from golem.core.variables import PAYMENT_DEADLINE

log = logging.getLogger(__name__)

# We reserve 30 minutes for the payment to go through
PAYMENT_MAX_DELAY = PAYMENT_DEADLINE - 30 * 60


def _make_batch_payments(
        payments: List[model.TaskPayment]
) -> List[golem_sci.Payment]:
    payees: defaultdict = defaultdict(lambda: 0)
    for p in payments:
        payees[p.wallet_operation.recipient_address] += \
            p.wallet_operation.amount
    res = []
    for payee, amount in payees.items():
        res.append(golem_sci.Payment(payee, amount))
    return res


class PaymentProcessor:
    CLOSURE_TIME_DELAY = 2
    # Don't try to use more than 75% of block gas limit
    BLOCK_GAS_LIMIT_RATIO = 0.75

    def __init__(self, sci) -> None:
        self._sci = sci
        self._gntb_reserved = 0
        self._awaiting = SortedListWithKey(key=lambda p: p.created_date)
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
        for sent_payment in model.TaskPayment \
                .select() \
                .join(model.WalletOperation) \
                .where(
                        model.WalletOperation.status == \
                        model.WalletOperation.STATUS.sent,
                ):
            if sent_payment.wallet_operation.tx_hash not in sent:
                sent[sent_payment.wallet_operation.tx_hash] = []
            sent[sent_payment.wallet_operation.tx_hash].append(sent_payment)
            self._gntb_reserved += sent_payment.wallet_operation.amount
        for tx_hash, payments in sent.items():
            self._sci.on_transaction_confirmed(
                tx_hash,
                lambda r, p=payments: threads.deferToThread(
                    self._on_batch_confirmed, p, r),
            )

        for awaiting_payment in model.TaskPayment \
                .select() \
                .join(model.WalletOperation) \
                .where(
                        model.WalletOperation.status.in_([
                            model.WalletOperation.STATUS.awaiting,
                            model.WalletOperation.STATUS.overdue,
                        ]),
                ):
            log.info(
                "Restoring awaiting payment for subtask %s to %s of %.6f GNTB",
                awaiting_payment.subtask,
                awaiting_payment.wallet_operation.recipient_address,
                awaiting_payment.wallet_operation.amount / denoms.ether,
            )
            self._awaiting.add(awaiting_payment)
            self._gntb_reserved += awaiting_payment.wallet_operation.amount

    def _on_batch_confirmed(
            self,
            payments: List[model.TaskPayment],
            receipt
    ) -> None:
        if not receipt.status:
            log.critical("Failed batch transfer: %s", receipt)
            for p in payments:
                wallet_operation = p.wallet_operation
                wallet_operation.status = model.WalletOperation.STATUS.awaiting
                wallet_operation.save()
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
            wallet_operation = p.wallet_operation
            wallet_operation.status = model.WalletOperation.STATUS.confirmed
            wallet_operation.gas_cost = fee
            wallet_operation.save()
            self._gntb_reserved -= p.wallet_operation.amount
            self._payment_confirmed(p, block.timestamp)

    @staticmethod
    def _payment_confirmed(payment: model.TaskPayment, timestamp: int) -> None:
        log.debug(
            "- %s confirmed fee: %.18f ETH",
            payment.subtask,
            payment.wallet_operation.gas_cost / denoms.ether
        )

        reference_date = datetime.datetime.fromtimestamp(timestamp)
        delay = (reference_date - payment.created_date).seconds

        dispatcher.send(
            signal="golem.payment",
            event="confirmed",
            subtask_id=payment.subtask,
            payee=payment.wallet_operation.recipient_address,
            delay=delay,
        )

    def add(
            self,
            task_header: dt_tasks.TaskHeader,
            subtask_id: str,
            eth_addr: str,
            value: int,
    ) -> int:
        log.info(
            "Adding payment for %s to %s (%.3f GNTB)",
            subtask_id,
            eth_addr,
            value / denoms.ether,
        )
        payment = model.TaskPayment.create(
            wallet_operation=model.WalletOperation.create(
                direction=model.WalletOperation.DIRECTION.outgoing,
                operation_type=model.WalletOperation.TYPE.task_payment,
                sender_address=self._sci.get_eth_address(),
                recipient_address=eth_addr,
                currency=model.WalletOperation.CURRENCY.GNT,
                amount=value,
            ),
            node=task_header.task_owner.key,
            task=task_header.task_id,
            subtask=subtask_id,
            expected_amount=value,
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
        gas_limit = self._sci.get_latest_confirmed_block().gas_limit * \
            self.BLOCK_GAS_LIMIT_RATIO
        payees = set()
        p: model.TaskPayment
        for p in self._awaiting:
            if p.processed_ts > closure_time:
                break
            gntb_balance -= p.wallet_operation.amount
            if gntb_balance < 0:
                log.debug(
                    'Insufficient GNTB balance.'
                    ' value=%(value).18f, subtask_id=%(subtask)s',
                    {
                        'value': p.wallet_operation.amount / denoms.ether,
                        'subtask': p.subtask,
                    },
                )
                break

            payees.add(p.wallet_operation.recipient_address)
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

        now = int(time.time())
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

        value = sum([p.wallet_operation.amount for p in payments])
        log.info("Batch payments value: %.3f GNTB", value / denoms.ether)

        closure_time = payments[-1].processed_ts
        tx_hash = self._sci.batch_transfer(
            _make_batch_payments(payments),
            closure_time,
        )
        del self._awaiting[:payments_count]

        for payment in payments:
            wallet_operation = payment.wallet_operation
            wallet_operation.status = model.WalletOperation.STATUS.sent
            wallet_operation.tx_hash = tx_hash
            wallet_operation.save()
            log.debug("- {} send to {} ({:.18f} GNTB)".format(
                payment.subtask,
                wallet_operation.recipient_address,
                wallet_operation.amount / denoms.ether))

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
            wallet_operation = payment.wallet_operation
            if wallet_operation.status is model.WalletOperation.STATUS.overdue:
                continue
            wallet_operation.status = model.WalletOperation.STATUS.overdue
            wallet_operation.save()
            log.debug("Marked as overdue. payment=%r", payment)
            counter += 1
        if counter:
            log.info("Marked %d payments as overdue.", counter)
