# -*- coding: utf-8 -*-
import logging
import time

from ethereum.utils import denoms
from pydispatch import dispatcher

from golem import model
from golem.core.variables import PAYMENT_DEADLINE

logger = logging.getLogger(__name__)


class IncomesKeeper:
    """Keeps information about payments received from other nodes
    """

    @staticmethod
    def received_transfer(
            tx_hash: str,
            sender_address: str,
            recipient_address: str,
            amount: int,
            currency,
    ):
        model.WalletOperation.create(
            tx_hash=tx_hash,
            direction=model.WalletOperation.DIRECTION.incoming,
            operation_type=model.WalletOperation.TYPE.transfer,
            status=model.WalletOperation.STATUS.confirmed,
            sender_address=sender_address,
            recipient_address=recipient_address,
            amount=amount,
            currency=currency,
            gas_cost=0,
        )

    @staticmethod
    def received_batch_transfer(
            tx_hash: str,
            sender: str,
            amount: int,
            closure_time: int,
            charged_from_deposit: bool = False,
    ) -> None:

        expected = model.TaskPayment.incomes().where(
            model.WalletOperation.sender_address == sender,
            model.TaskPayment.accepted_ts > 0,
            model.TaskPayment.accepted_ts <= closure_time,
            model.WalletOperation.tx_hash.is_null(),
            model.TaskPayment.settled_ts.is_null(),
        )

        expected_value = sum([e.missing_amount for e in expected])
        if expected_value == 0:
            # Probably already handled event
            return

        if expected_value != amount:
            logger.warning(
                'Batch transfer amount does not match, expected %r, got %r',
                expected_value / denoms.ether,
                amount / denoms.ether)

        amount_left = amount

        for e in expected:
            received = min(amount_left, e.expected_amount)
            e.wallet_operation.amount += received
            amount_left -= received
            e.wallet_operation.tx_hash = tx_hash
            e.wallet_operation.status = model.WalletOperation.STATUS.confirmed
            e.wallet_operation.save()
            e.charged_from_deposit = charged_from_deposit
            e.save()

            if e.missing_amount == 0:
                dispatcher.send(
                    signal='golem.income',
                    event='confirmed',
                    node_id=e.wallet_operation.sender_address,
                    amount=e.wallet_operation.amount,
                )

    def received_forced_payment(
            self,
            tx_hash: str,
            sender: str,
            amount: int,
            closure_time: int) -> None:
        logger.info(
            "Received forced payment from %s",
            sender,
        )
        self.received_batch_transfer(
            tx_hash=tx_hash,
            sender=sender,
            amount=amount,
            closure_time=closure_time,
            charged_from_deposit=True,
        )

    @staticmethod
    def expect(  # pylint: disable=too-many-arguments
            sender_node: str,
            task_id: str,
            subtask_id: str,
            payer_address: str,
            my_address: str,
            value: int,
            accepted_ts: int) -> model.TaskPayment:
        logger.info(
            "Expected income - sender_node: %s, subtask: %s, "
            "payer: %s, value: %f",
            sender_node,
            subtask_id,
            payer_address,
            value / denoms.ether,
        )
        income = model.TaskPayment.create(
            wallet_operation=model.WalletOperation.create(
                direction=model.WalletOperation.DIRECTION.incoming,
                operation_type=model.WalletOperation.TYPE.task_payment,
                status=model.WalletOperation.STATUS.awaiting,
                sender_address=payer_address,
                recipient_address=my_address,
                amount=0,
                currency=model.WalletOperation.CURRENCY.GNT,
                gas_cost=0,
            ),
            node=sender_node,
            task=task_id,
            subtask=subtask_id,
            expected_amount=value,
            accepted_ts=accepted_ts,
        )
        dispatcher.send(
            signal='golem.income',
            event='created',
            subtask_id=subtask_id,
            amount=value
        )

        return income

    @staticmethod
    def settled(
            sender_node: str,
            subtask_id: str,
            settled_ts: int) -> None:
        try:
            income = model.TaskPayment.get(node=sender_node, subtask=subtask_id)
        except model.TaskPayment.DoesNotExist:
            logger.error(
                "TaskPayment.DoesNotExist subtask_id: %r", subtask_id)
            return

        income.settled_ts = settled_ts
        income.save()

    @staticmethod
    def received_forced_subtask_payment(
            tx_hash: str,
            sender_addr: str,
            subtask_id: str,
            value: int) -> None:
        model.TaskPayment.create(
            wallet_operation=model.WalletOperation.create(
                tx_hash=tx_hash,
                direction=model.WalletOperation.DIRECTION.incoming,
                operation_type=model.WalletOperation.TYPE.deposit_payment,
                status=model.WalletOperation.STATUS.confirmed,
                sender_address=sender_addr,
                recipient_address="",
                amount=value,
                currency=model.WalletOperation.CURRENCY.GNT,
                gas_cost=0,
            ),
            node="",
            task="",
            subtask=subtask_id,
            expected_amount=value,
            charged_from_deposit=True,
        )

    @staticmethod
    def get_list_of_all_incomes():
        # TODO: pagination. issue #2402
        return model.TaskPayment.incomes(
        ).order_by(model.TaskPayment.created_date.desc())

    @staticmethod
    def update_overdue_incomes() -> None:
        """
        Set overdue flag for all incomes that have been waiting for too long.
        :return: Updated incomes
        """
        accepted_ts_deadline = int(time.time()) - PAYMENT_DEADLINE

        incomes = list(model.TaskPayment.incomes().where(
            model.WalletOperation.status !=
            model.WalletOperation.STATUS.overdue,
            model.WalletOperation.tx_hash.is_null(True),
            model.TaskPayment.accepted_ts < accepted_ts_deadline,
        ))

        if not incomes:
            return

        for income in incomes:
            income.wallet_operation.status = \
                model.WalletOperation.STATUS.overdue
            income.wallet_operation.save()
            dispatcher.send(
                signal='golem.income',
                event='overdue_single',
                node_id=income.node,
            )

        dispatcher.send(
            signal='golem.income',
            event='overdue',
            incomes=incomes,
        )
