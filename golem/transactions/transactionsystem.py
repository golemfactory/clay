import logging

from paymentskeeper import PaymentInfo, PaymentsKeeper
from incomeskeeper import IncomesKeeper

logger = logging.getLogger(__name__)


class TransactionSystem(object):
    """ Transaction system. Keeps information about budget, expected payments, etc. """

    def __init__(self, node_id, payments_keeper_class=PaymentsKeeper, incomes_keeper_class=IncomesKeeper):
        """ Create new transaction system instance for node with given id
        :param node_id: id of a node that has this transaction system
        :param payments_keeper_class: default PaymentsKeeper, payment keeper class, an instance of this class
        while be used as a payment keeper
        """
        self.node_id = node_id
        self.payments_keeper = payments_keeper_class()  # Keeps information about payments to send
        self.incomes_keeper = incomes_keeper_class()  # Keeps information about received payments
        self.budget = 10000  # TODO Add method that set proper budget value

    def get_income(self, addr_info, value):
        """ Increase information about budget with reward
        :param str addr_info: return information about address of a node that send this payment
        :param int value: value of the payment
        """
        self.budget += value
        self.incomes_keeper.get_income(addr_info, value)

    def add_payment_info(self, task_id, subtask_id, value, account_info):
        """ Add to payment keeper information about new payment for subtask
        :param str task_id: id of a task that this payment is apply to
        :param str subtask_id: if of a subtask that this payment is apply to (node finished computation for that subtask)
        :param int value: valuation of a given subtask
        :param AccountInfo account_info: billing account for a node that has computed a task
        """
        payment_info = PaymentInfo(task_id, subtask_id, value, account_info)
        self.payments_keeper.finished_subtasks(payment_info)

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

    def add_to_waiting_payments(self, task_id, node_id, value):
        return self.incomes_keeper.add_waiting_payment(task_id, node_id, expected_value=value)

    def pay_for_task(self, task_id, payments):
        """ Pay for task using specific system. This method should be implemented in derived classes
        :param str task_id: finished task
        :param payments: payments representation
        """
        raise NotImplementedError

    def check_payments(self):
        # TODO Some code from taskkeeper
        # now = datetime.datetime.now()
        # after_deadline = []
        # for subtask_id, [task_id, task_date, deadline] in self.completed.items():
        #     if deadline < now:
        #         after_deadline.append(task_id)
        #         del self.completed[subtask_id]
        # return after_deadline

        return []
