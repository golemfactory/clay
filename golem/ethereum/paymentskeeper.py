import logging
from datetime import datetime
from typing import Iterable, Tuple, Optional

from eth_utils import encode_hex

from golem.core.common import to_unicode, datetime_to_timestamp_utc
from golem.model import Payment, PaymentStatus

logger = logging.getLogger(__name__)


class PaymentsDatabase(object):
    """ Save and retrieve from database information about payments that this node has to make / made
    """

    @staticmethod
    def get_payment_value(subtask_id: str):
        """ Return value of a payment that was done to the same node and for the same task as payment for payment_info
        """
        return PaymentsDatabase.get_payment_for_subtask(subtask_id)

    @staticmethod
    def get_payment_for_subtask(subtask_id):
        try:
            return Payment.get(Payment.subtask == subtask_id).value
        except Payment.DoesNotExist:
            logger.debug("Can't get payment value - payment does not exist")
            return 0

    @staticmethod
    def get_total_payment_for_subtasks(subtask_ids: Iterable[str])\
            -> Tuple[Optional[int], Optional[int]]:
        """
        Get total value and total fee for payments for the given subtask IDs
        **if all payments for the given subtasks are sent**
        :param subtask_ids: subtask IDs
        :return: (total_value, total_fee) if all payments are sent,
                (None, None) otherwise
        """
        payments = Payment.select(
            Payment.value,
            Payment.details,
            Payment.status
        ).where(
            Payment.subtask.in_(subtask_ids),
        )
        all_sent = all(
            p.status in [PaymentStatus.sent, PaymentStatus.confirmed]
            for p in payments)
        if not payments or not all_sent:
            return None, None

        # Because details are JSON field
        return sum(p.value or 0 for p in payments), \
            sum(p.details.fee or 0 for p in payments)

    @staticmethod
    def add_payment(subtask_id: str, eth_address: bytes, value: int):
        """ Add new payment to the database.
        :param payment_info:
        """
        Payment.create(subtask=subtask_id,
                       payee=eth_address,
                       value=value)

    def change_state(self, subtask_id, state):
        """ Change state for all payments for task_id
        :param str subtask_id: change state of all payments that should be done for computing this task
        :param state: new state
        :return:
        """
        # FIXME: Remove this method #2457
        query = Payment.update(status=state, modified_date=str(datetime.now()))
        query = query.where(Payment.subtask == subtask_id)
        query.execute()

    def get_state(self, payment_info):
        """ Return state of a payment for given task that should be / was made to given node
        :return str|None: return state of payment or none if such payment don't exist in database
        """
        # FIXME: Remove this method #2457
        try:
            return Payment.get(Payment.subtask == payment_info.subtask_id).status
        except Payment.DoesNotExist:
            logger.warning("Payment for subtask {} to node {} does not exist"
                           .format(payment_info.subtask_id, payment_info.computer.key_id))
            return None

    @staticmethod
    def get_newest_payment(num=30):
        """ Return specific number of recently modified payments
        :param num: number of payments to return
        :return:
        """
        query = Payment.select().order_by(Payment.modified_date.desc()).limit(num)
        return query.execute()


class PaymentsKeeper:
    """ Keeps information about payments for tasks that should be processed and send or received. """

    def __init__(self) -> None:
        """ Create new payments keeper instance"""
        self.db = PaymentsDatabase()

    def get_list_of_all_payments(self):
        # This data is used by UI.
        return [{
            "subtask": to_unicode(payment.subtask),
            "payee": to_unicode(encode_hex(payment.payee)),
            "value": to_unicode(payment.value),
            "status": to_unicode(payment.status.name),
            "fee": to_unicode(payment.details.fee),
            "block_number": to_unicode(payment.details.block_number),
            "transaction": to_unicode(payment.details.tx),
            "created": datetime_to_timestamp_utc(payment.created_date),
            "modified": datetime_to_timestamp_utc(payment.modified_date)
        } for payment in self.db.get_newest_payment()]

    def finished_subtasks(
            self,
            subtask_id: str,
            eth_address: bytes,
            value: int):
        """ Add new information about finished subtask
        :param PaymentInfo payment_info: full information about payment for given subtask
        """
        self.db.add_payment(subtask_id, eth_address, value)

    def get_payment(self, subtask_id):
        """
        Get cost of subtasks defined by @subtask_id
        :param subtask_id: Subtask ID
        :return: Cost of the @subtask_id
        """
        return self.db.get_payment_for_subtask(subtask_id)

    def get_total_payment_for_subtasks(self, subtask_ids: Iterable[str]) \
            -> Tuple[Optional[int], Optional[int]]:
        """
        Get total value and total fee for payments for the given subtask IDs
        **if all payments for the given subtasks are sent**
        :param subtask_ids: subtask IDs
        :return: (total_value, total_fee) if all payments are sent,
                (None, None) otherwise
        """
        return self.db.get_total_payment_for_subtasks(subtask_ids)
