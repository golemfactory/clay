from golem.model import Payment

from paymentskeeper import PaymentsKeeper
from incomeskeeper import IncomesKeeper


class TransactionSystem(object):
    """ Transaction system. Keeps information about budget, expected payments, etc. """

    def __init__(self, payments_keeper_class=PaymentsKeeper, incomes_keeper_class=IncomesKeeper):
        """ Create new transaction system instance.
        :param payments_keeper_class: default PaymentsKeeper, payment keeper class, an instance of this class
        while be used as a payment keeper
        """
        self.payments_keeper = payments_keeper_class()  # Keeps information about payments to send
        self.incomes_keeper = incomes_keeper_class()  # Keeps information about received payments

    def get_income(self, addr_info, value):
        """ Increase information about budget with reward
        :param str addr_info: return information about address of a node that send this payment
        :param int value: value of the payment
        """
        self.incomes_keeper.get_income(addr_info, value)

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
            raise ValueError("Incorrect 'payee' length: {}. Should be 20".format(len(payee)))
        return Payment.create(subtask=subtask_id, payee=payee, value=value)

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

    def check_payments(self):
        # TODO Some code from taskkeeper
        # now = datetime.datetime.now()
        # after_deadline = []
        # for subtask_id, [task_id, task_date, deadline] in self.completed.items():
        #     if deadline < now:
        #         after_deadline.append(task_id)
        #         del self.completed[subtask_id]
        # return after_deadline

        self.incomes_keeper.run_once()
        return []

    def sync(self):
        pass
