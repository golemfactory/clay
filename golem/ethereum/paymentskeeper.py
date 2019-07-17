import datetime
import logging
from typing import Iterable, List, Optional

from golem import model
from golem.core.common import to_unicode, datetime_to_timestamp_utc

logger = logging.getLogger(__name__)


class PaymentsDatabase(object):
    """Save and retrieve from database information
       about payments that this node has to make / made
    """

    @staticmethod
    def get_payment_value(subtask_id: str):
        """Returns value of a payment
           that was done to the same node and for the same
           task as payment for payment_info
        """
        return PaymentsDatabase.get_payment_for_subtask(subtask_id)

    @staticmethod
    def get_payment_for_subtask(subtask_id):
        try:
            return model.TaskPayment.get(
                model.TaskPayment.subtask == subtask_id,
            ).wallet_operation.amount
        except model.TaskPayment.DoesNotExist:
            logger.debug("Can't get payment value - payment does not exist")
            return 0

    @staticmethod
    def get_subtasks_payments(
            subtask_ids: Iterable[str],
    ) -> List[model.TaskPayment]:
        return list(
            model.TaskPayment.payments().where(
                model.TaskPayment.subtask.in_(subtask_ids),
            )
        )

    @staticmethod
    def get_newest_payment(num: Optional[int] = None,
                           interval: Optional[datetime.timedelta] = None):
        """ Return specific number of recently modified payments
        :param num: Number of payments to return. Unlimited if None.
        :param interval: Return payments from last interval of time. Unlimited
                         if None.
        :return:
        """
        query = model.TaskPayment.payments().order_by(
            model.WalletOperation.modified_date.desc(),
        )

        if interval is not None:
            then = datetime.datetime.now(tz=datetime.timezone.utc) - interval
            query = query.where(
                model.WalletOperation.modified_date >= then,
            )

        if num is not None:
            query = query.limit(num)

        return query.execute()


class PaymentsKeeper:
    """Keeps information about outgoing payments
       that should be processed and send or received.
    """

    def __init__(self) -> None:
        """ Create new payments keeper instance"""
        self.db = PaymentsDatabase()

    def get_list_of_all_payments(self, num: Optional[int] = None,
                                 interval: Optional[datetime.timedelta] = None):
        # This data is used by UI.
        return [{
            "subtask": to_unicode(payment.subtask),
            "payee": to_unicode(payment.wallet_operation.recipient_address),
            "value": to_unicode(payment.wallet_operation.amount),
            "status": to_unicode(payment.wallet_operation.status.name),
            "fee": to_unicode(payment.wallet_operation.gas_cost),
            "block_number": '',
            "transaction": to_unicode(payment.wallet_operation.tx_hash),
            "node": payment.node,
            "created": datetime_to_timestamp_utc(payment.created_date),
            "modified": datetime_to_timestamp_utc(
                payment.wallet_operation.modified_date,
            )
        } for payment in self.db.get_newest_payment(num, interval)]

    def get_payment(self, subtask_id):
        """
        Get cost of subtasks defined by @subtask_id
        :param subtask_id: Subtask ID
        :return: Cost of the @subtask_id
        """
        return self.db.get_payment_for_subtask(subtask_id)

    def get_subtasks_payments(
            self,
            subtask_ids: Iterable[str]) -> List[model.TaskPayment]:
        return self.db.get_subtasks_payments(subtask_ids)

    @staticmethod
    def confirmed_transfer(
            tx_hash: str,
            successful: bool,
            gas_cost: int,
    ) -> None:
        try:
            operation = model.WalletOperation.select() \
                .where(
                    model.WalletOperation.tx_hash == tx_hash,
                ).get()
        except model.WalletOperation.DoesNotExist:
            logger.warning(
                "Got confirmation of unknown transfer. tx_hash=%s",
                tx_hash,
            )
            return
        if not successful:
            logger.error("Failed transaction. tx_hash=%s", tx_hash)
            operation.on_failed(gas_cost=gas_cost)
            operation.save()
            return
        operation.on_confirmed(gas_cost=gas_cost)
        operation.save()
