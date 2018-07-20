from typing import List, Iterable, Tuple, Optional

from golem.core.common import datetime_to_timestamp_utc, to_unicode
from golem.core.service import LoopingCallService
from golem.model import Payment, PaymentStatus, PaymentDetails

from .paymentskeeper import PaymentsKeeper
from .incomeskeeper import IncomesKeeper


class TransactionSystem(LoopingCallService):
    """ Transaction system.
    Keeps information about budget, expected payments, etc. """

    def __init__(self, payments_keeper=PaymentsKeeper(),
                 incomes_keeper=IncomesKeeper()):
        """ Create new transaction system instance.
        :param payments_keeper:
        default PaymentsKeeper, payment keeper class,
        an instance of this class
        while be used as a payment keeper
        """

        # Keeps information about payments to send
        self.payments_keeper = payments_keeper

        # Keeps information about received payments
        self.incomes_keeper = incomes_keeper

        super().__init__(13)

    def add_payment_info(self, task_id, subtask_id, value, account_info):
        """ Add to payment keeper information about new payment for subtask.
        :param str task_id:    ID if a task the payment is related to.
        :param str subtask_id: the id of the compleated
                               subtask this payment is for.
        :param int value:      Aggreed value of the computed subtask.
        :param AccountInfo account_info: Billing account.
        :raise ValueError:     In case of incorrect payee address
        """
        payee = account_info.eth_account.address
        if len(payee) != 20:
            raise ValueError(
                "Incorrect 'payee' length: {}. Should be 20".format(len(payee)))
        return Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value,
            details=PaymentDetails(
                node_info=account_info.node_info,
            )
        )

    def get_payments_list(self):
        """ Return list of all planned and made payments
        :return list: list of dictionaries describing payments
        """
        return self.payments_keeper.get_list_of_all_payments()

    def get_total_payment_for_subtasks(self, subtask_ids: Iterable[str]) \
            -> Tuple[Optional[int], Optional[int]]:
        """
        Get total value and total fee for payments for the given subtask IDs
        **if all payments for the given subtasks are sent**
        :param subtask_ids: subtask IDs
        :return: (total_value, total_fee) if all payments are sent,
                (None, None) otherwise
        """
        return self.payments_keeper.get_total_payment_for_subtasks(subtask_ids)

    def get_incomes_list(self):
        """ Return list of all expected and received incomes
        :return list: list of dictionaries describing incomes
        """
        return self.incomes_keeper.get_list_of_all_incomes()

    def get_incoming_payments(self):
        """Returns preprocessed list of pending & confirmed incomes.
        It's optimised for electron GUI.
        """
        incomes = self.incomes_keeper.get_list_of_all_incomes()

        def item(o):
            status = PaymentStatus.confirmed if o.transaction \
                else PaymentStatus.awaiting

            return {
                "subtask": to_unicode(o.subtask),
                "payer": to_unicode(o.sender_node),
                "value": to_unicode(o.value),
                "status": to_unicode(status.name),
                "transaction": to_unicode(o.transaction),
                "created": datetime_to_timestamp_utc(o.created_date),
                "modified": datetime_to_timestamp_utc(o.modified_date)
            }

        return [item(income) for income in incomes]

    def get_nodes_with_overdue_payments(self) -> List[str]:
        overdue_incomes = self.incomes_keeper.update_overdue_incomes()
        return [x.sender_node for x in overdue_incomes]

    def sync(self) -> None:
        pass
