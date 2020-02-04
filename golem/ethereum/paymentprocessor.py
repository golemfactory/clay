import datetime
import logging

from collections import defaultdict
from typing import (
    List,
)

from ethereum.utils import denoms
from pydispatch import dispatcher
from sortedcontainers import SortedListWithKey
from twisted.internet import threads

import golem_sci

from golem import model
from golem.core import common
from golem.core.variables import PAYMENT_DEADLINE
PAYMENT_DEADLINE_TD = datetime.timedelta(seconds=PAYMENT_DEADLINE)

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
        self.last_print_time = datetime.datetime.min.replace(
            tzinfo=datetime.timezone.utc,
        )

    @property
    def recipients_count(self) -> int:
        return len(self._awaiting)

    @property
    def reserved_gntb(self) -> int:
        return self._gntb_reserved

    def load_from_db(self):
        sent = {}
        for sent_payment in model.TaskPayment \
                .payments() \
                .where(
                        model.WalletOperation.status ==
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
                .payments() \
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

        reference_date = datetime.datetime.fromtimestamp(
            timestamp,
            tz=datetime.timezone.utc,
        )
        delay = (reference_date - payment.created_date).seconds

        dispatcher.send(
            signal="golem.payment",
            event="confirmed",
            subtask_id=payment.subtask,
            payee=payment.wallet_operation.recipient_address,
            delay=delay,
        )

    def add(  # pylint: disable=too-many-arguments
            self,
            node_id: str,
            task_id: str,
            subtask_id: str,
            eth_addr: str,
            value: int,
    ) -> model.TaskPayment:
        log.info(
            "Adding payment. subtask_id=%s, receiver=%s, value=(%.18f GNTB)",
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
                status=model.WalletOperation.STATUS.awaiting,
                gas_cost=0,
            ),
            node=node_id,
            task=task_id,
            subtask=subtask_id,
            expected_amount=value,
            charged_from_deposit=False,
        )

        self._awaiting.add(payment)
        self._gntb_reserved += value

        log.info("Reserved %.3f GNTB", self._gntb_reserved / denoms.ether)
        return payment

    def __get_next_batch(self, closure_time: datetime.datetime) -> int:
        gntb_balance = self._sci.get_gntb_balance(self._sci.get_eth_address())
        eth_balance = self._sci.get_eth_balance(self._sci.get_eth_address())
        gas_price = self._sci.get_current_gas_price()

        ind = 0
        gas_limit = self._sci.get_latest_confirmed_block().gas_limit * \
            self.BLOCK_GAS_LIMIT_RATIO
        payees = set()
        p: model.TaskPayment
        for p in self._awaiting:
            if p.created_date > closure_time:
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

        # we need to take either all payments with given created_date or none
        if ind < len(self._awaiting):
            while ind > 0 and self._awaiting[ind - 1]\
                    .created_date == self._awaiting[ind].created_date:
                ind -= 1

        return ind

    def sendout(self, acceptable_delay: int = PAYMENT_MAX_DELAY):
        if not self._awaiting:
            return False

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        deadline = self._awaiting[0].created_date +\
            datetime.timedelta(seconds=acceptable_delay)
        if deadline > now:
            if now > self.last_print_time + datetime.timedelta(minutes=5):
                log.info("Next sendout at %s", deadline)
                self.last_print_time = now
            return False

        payments_count = self.__get_next_batch(
            now - datetime.timedelta(seconds=self.CLOSURE_TIME_DELAY),
        )
        if payments_count == 0:
            return False
        payments = self._awaiting[:payments_count]

        value = sum([p.wallet_operation.amount for p in payments])
        log.info("Batch payments value: %.18f GNTB", value / denoms.ether)

        closure_time = int(
            payments[-1].created_date.replace(
                tzinfo=datetime.timezone.utc,
            ).timestamp()
        )
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

        created_deadline = datetime.datetime.now(
            tz=datetime.timezone.utc
        ) - PAYMENT_DEADLINE_TD
        counter = 0
        for payment in self._awaiting:
            if payment.created_date >= created_deadline:
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

    def sent_forced_subtask_payment(
            self,
            tx_hash: str,
            receiver: str,
            subtask_id: str,
            amount: int,
    ) -> None:
        log.warning(
            "Concent payed on our behalf."
            " type='subtask payment', amount: %s, tx_hash: %s,"
            " receiver=%s",
            amount,
            tx_hash,
            receiver,
        )
        for awaiting_payment in self._awaiting[:]:
            if awaiting_payment.subtask == subtask_id:
                self._awaiting.remove(awaiting_payment)
        query = model.TaskPayment.select() \
            .where(
                model.TaskPayment.subtask == subtask_id,
            )
        if not query.exists():
            log.info(
                "Concent payed for something that is missing in our DB."
                " tx_hash: %s, subtask_id: %s",
                tx_hash,
                subtask_id,
            )
            return

        for old_payment in query:
            old_payment.wallet_operation.status = \
                model.WalletOperation.STATUS.arbitraged_by_concent
            old_payment.wallet_operation.save()

            # Create Concent TP
            model.TaskPayment.create(
                wallet_operation=model.WalletOperation.create(
                    tx_hash=tx_hash,
                    direction=model.WalletOperation.DIRECTION.outgoing,
                    operation_type=model.WalletOperation.TYPE.deposit_payment,
                    sender_address=self._sci.get_eth_address(),
                    recipient_address=receiver,
                    currency=model.WalletOperation.CURRENCY.GNT,
                    amount=amount,
                    status=model.WalletOperation.STATUS.confirmed,
                    gas_cost=0,
                ),
                node=old_payment.node,
                task=old_payment.task,
                subtask=subtask_id,
                expected_amount=amount,
                charged_from_deposit=True,
            )

    def sent_forced_payment(
            self,
            tx_hash: str,
            receiver: str,
            amount: int,
            closure_time: int,
    ) -> None:
        closure_dt = common.timestamp_to_datetime(closure_time)
        log.warning(
            "Concent payed on our behalf."
            " type=batch-payment, amount: %s, tx_hash: %s"
            " receiver=%s, closure_dt=%s",
            amount,
            tx_hash,
            receiver,
            closure_dt,
        )
        for awaiting_payment in self._awaiting[:]:
            if awaiting_payment.created_date <= closure_dt:
                self._awaiting.remove(awaiting_payment)
        # Find unpaid TPs within closure_time
        query = model.TaskPayment.select() \
            .where(
                model.TaskPayment.created_date <= closure_dt,
            )
        if not query.exists():
            log.info(
                "Concent payed for something that is missing in our DB."
                " tx_hash: %s",
                tx_hash,
            )
            return

        for old_payment in query:
            old_payment.wallet_operation.status = \
                model.WalletOperation.STATUS.arbitraged_by_concent
            old_payment.wallet_operation.save()

            # Create Concent TP
            model.TaskPayment.create(
                wallet_operation=model.WalletOperation.create(
                    tx_hash=tx_hash,
                    direction=model.WalletOperation.DIRECTION.outgoing,
                    operation_type=model.WalletOperation.TYPE.deposit_payment,
                    sender_address=self._sci.get_eth_address(),
                    recipient_address=receiver,
                    currency=model.WalletOperation.CURRENCY.GNT,
                    amount=amount,
                    status=model.WalletOperation.STATUS.confirmed,
                    gas_cost=0,
                ),
                node=old_payment.node,
                task=old_payment.task,
                subtask=old_payment.subtask,
                expected_amount=amount,
                charged_from_deposit=True,
            )
