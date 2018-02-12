from golem.core.common import datetime_to_timestamp, to_unicode
from golem.model import Payment, PaymentStatus, PaymentDetails

from .paymentskeeper import PaymentsKeeper
from .incomeskeeper import IncomesKeeper


class TransactionSystem(object):
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
                "created": datetime_to_timestamp(o.created_date),
                "modified": datetime_to_timestamp(o.modified_date)
            }

        return [item(income) for income in incomes]

    def check_payments(self):
        # TODO Some code from taskkeeper
        # now = datetime.datetime.now()
        # after_deadline = []
        # for subtask_id, [task_id, task_date, deadline]
        # in self.completed.items():
        #     if deadline < now:
        #         after_deadline.append(task_id)
        #         del self.completed[subtask_id]
        # return after_deadline

        self.incomes_keeper.run_once()
        return []

    def sync(self) -> None:
        pass
