import logging
from datetime import datetime

from collections import deque
from peewee import IntegrityError

from golem.model import Payment, db

logger = logging.getLogger(__name__)


class PaymentsDatabase(object):
    """ Save and retrieve from database information about payments that this node has to make / made
    """

    def get_payment_value(self, payment_info):
        """ Return value of a payment that was done to the same node and for the same task as payment for payment_info
        :param PaymentInfo payment_info: payment structure from which the database should retrieve information about
         computing node and task id.
        :return int: value of a previous similiar payment or 0 if there is no such payment in database
        """
        try:
            return Payment.select(Payment.val).where(self.__same_transaction(payment_info)).get().val
        except Payment.DoesNotExist:
            logger.warning("Can't get payment value - payment does not exist")
            return 0

    def add_payment(self, payment_info):
        """ Add new payment to the database. If the payment already existed than add new payment value
        to the old value.
        :param payment_info:
        """
        try:
            with db.transaction():
                Payment.create(to_node_id=payment_info.computer.key_id,
                               task=payment_info.task_id,
                               val=payment_info.value,
                               state=PaymentState.waiting_to_be_paid)
        except IntegrityError:
            query = Payment.update(val=payment_info.value + Payment.val, modified_date=str(datetime.now()))
            query.where(self.__same_transaction(payment_info)).execute()

    def change_state(self, task_id, state):
        """ Change state for all payments for task_id
        :param str task_id: change state of all payments that should be done for computing this task
        :param state: new state
        :return:
        """
        query = Payment.update(state=state, modified_date=str(datetime.now()))
        query = query.where(Payment.task == task_id)
        query.execute()

    def get_state(self, payment_info):
        """ Return state of a payment for given task that should be / was made to given node
        :return str|None: return state of payment or none if such payment don't exist in database
        """
        try:
            return Payment.select().where(self.__same_transaction(payment_info)).get().state
        except Payment.DoesNotExist:
            logger.warning("Payment for task {} to node {} does not exist".format(payment_info.task_id,
                                                                                  payment_info.computer.key_id))
            return None

    @staticmethod
    def get_newest_payment(num=30):
        """ Return specific number of recently modified payments
        :param num: number of payments to return
        :return:
        """
        query = Payment.select().order_by(Payment.modified_date.desc()).limit(num)
        return query.execute()

    @staticmethod
    def __same_transaction(payment_info):
        return (Payment.task == payment_info.task_id) & (Payment.to_node_id == payment_info.computer.key_id)


class PaymentsKeeper(object):
    """ Keeps information about payments for tasks that should be processed and send or received. """

    def __init__(self):
        """ Create new payments keeper instance"""
        # be waiting for last subtask value estimation
        self.tasks_to_pay = deque()  # finished tasks with payments have been processed but haven't been send yet
        self.settled_tasks = {}  # finished tasks with payments that has been pass to task server
        self.db = PaymentsDatabase()

    #   self.load_from_database()

    def payment_failure(self, task_id):
        """ React to the fact that payment operation for task with given id failed. Remove given task form list of
        settled tasks
        :param task_id: payment for this task failed
        """
        task = self.settled_tasks.get(task_id)
        if task is None:
            logger.error("Unknown payment for task {}".format(task_id))
            return
        self.db.change_state(task_id, PaymentState.waiting_to_be_paid)
        self.tasks_to_pay.append(task)
        del self.settled_tasks[task_id]

    def get_list_of_all_payments(self):
        return self.load_from_database()

    def finished_subtasks(self, payment_info):
        """ Add new information about finished subtask
        :param PaymentInfo payment_info: full information about payment for given subtask
        """
        task = TaskPaymentInfo(payment_info.task_id)
        self.db.add_payment(payment_info)
        task.subtasks[payment_info.subtask_id] = SubtaskPaymentInfo(payment_info.value, payment_info.computer)
        task.value += payment_info.value
        self.tasks_to_pay.append(task)

    def load_from_database(self):
        return [{"task": payment.task, "node": payment.to_node_id, "value": payment.val, "state": payment.state} for
                payment in self.db.get_newest_payment()]

    @staticmethod
    def __get_nodes_grouping(subtasks):
        nodes = {}
        for subtask in subtasks.itervalues():
            if subtask.computer.key_id in nodes:
                nodes[subtask.computer.key_id] += subtask.value
            else:
                nodes[subtask.computer.key_id] = subtask.value
        return nodes

    def __change_nodes_to_payment_info(self, values, name):
        payments = []
        for task in values:
            nodes = self.__get_nodes_grouping(task.subtasks)
            for node_id, value in nodes.iteritems():
                payments.append({"task": task.task_id, "node": node_id, "value": value, "state": name})
        return payments


class PaymentState(object):
    waiting_to_be_paid = "Waiting for processing"
    settled = "Finished"


class PaymentInfo(object):
    """ Full information about payment for a subtask. Include task id, subtask payment information and
    account information about node that has computed this task. """
    def __init__(self, task_id, subtask_id, value, computer):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.value = value
        self.computer = computer


class TaskPaymentInfo(object):
    """ Information about reward for task """
    def __init__(self, task_id):
        self.task_id = task_id
        self.subtasks = {}
        self.value = 0


class SubtaskPaymentInfo(object):
    """ Information about reward for subtask """
    def __init__(self, value, computer):
        self.value = value
        self.computer = computer


class AccountInfo(object):
    """ Information about node's payment account """
    def __init__(self, key_id, port, addr, node_name, node_info):
        self.key_id = key_id
        self.port = port
        self.addr = addr
        self.node_name = node_name
        self.node_info = node_info

    def __eq__(self, other):
        if type(other) is type(self):
            return self.key_id == other.key_id
        return False
