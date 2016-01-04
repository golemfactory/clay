import logging
from collections import deque

logger = logging.getLogger(__name__)


class PaymentsKeeper(object):
    """ Keeps information about payments for tasks that should be processed and send or received. """

    def __init__(self):
        """ Create new payments keeper instance"""
        self.computing_tasks = {}  # tasks that are computed right now
        self.finished_tasks = []  # tasks that are finished and they're payment haven't been processed yet (may still
        # be waiting for last subtask value estimation
        self.tasks_to_pay = deque()  # finished tasks with payments have been processed but haven't been send yet
        self.waiting_for_payments = {}  # should receive payments from this dict
        self.settled_tasks = {}  # finished tasks with payments that has been pass to task server

    def task_finished(self, task_id):
        """ Add id of a task to the list of finished tasks
        :param task_id: finished task id
        """
        self.finished_tasks.append(task_id)

    def payment_failure(self, task_id):
        """ React to the fact that payment operation for task with given id failed. Remove given task form list of
        settled tasks
        :param task_id: payment for this task failed
        """
        task = self.settled_tasks.get(task_id)
        if task is None:
            logger.error("Unknown payment for task {}".format(task_id))
            return
        self.tasks_to_pay.append(task)
        del self.settled_tasks[task_id]

    def get_new_payments_task(self, budget):
        """ Return new payment for a computed task that hasn't been processed yet and that is not higher than node's
        budget
        :param int budget: current node's budget
        :return tuple: return task id and list of payments for this task or a pair with two None
        """
        if len(self.tasks_to_pay) > 0:
            task = self.tasks_to_pay.popleft()
            if task.value < budget:
                self.settled_tasks[task.task_id] = task
                return task, self.get_list_of_payments(task)
            else:
                self.tasks_to_pay.append(task)
        else:
            return None, None

    def get_list_of_payments(self, task):
        """ Extract information about subtask payment from given task payment info
        :param TaskPaymentInfo task: information about payments for a task
        :return dict: dictionary with information about subtask payments
        """
        return task.subtasks

    def get_list_of_all_payments(self):
        #FIXME
        all_payments = []
        for task in self.tasks_to_pay:
            nodes = self.__get_nodes_grouping(task.subtasks)
            for node_id, value in nodes.iteritems():
                all_payments.append({"task": task.task_id, "node": node_id, "amount": value, "date": "WAITING"})
        for task in self.finished_tasks:
            nodes = self.__get_nodes_grouping(task.subtasks)
            for node_id, value in nodes.iteritems():
                all_payments.append({"task": task.task_id, "node": node_id, "amount": value, "date": "FINISHED"})
        for task in self.settled_tasks.itervalues():
            nodes = self.__get_nodes_grouping(task.subtasks)
            for node_id, value in nodes.iteritems():
                all_payments.append({"task": task.task_id, "node": node_id, "amount": value, "date": "SETTLED"})
        for task in self.computing_tasks.itervalues():
            nodes = self.__get_nodes_grouping(task.subtasks)
            for node_id, value in nodes.iteritems():
                all_payments.append({"task": task.task_id, "node": node_id, "amount": value, "date": "COMPUTING"})
        return all_payments

    def finished_subtasks(self, payment_info):
        """ Add new information about finished subtask
        :param PaymentInfo payment_info: full information about payment for given subtask
        """
        task = self.computing_tasks.setdefault(payment_info.task_id, TaskPaymentInfo(payment_info.task_id))
        task.subtasks[payment_info.subtask_id] = SubtaskPaymentInfo(payment_info.value, payment_info.computer)
        task.value += payment_info.value
        if payment_info.task_id in self.finished_tasks:
            self.finished_tasks.remove(payment_info.task_id)
            self.__put_task_in_tasks_to_pay(payment_info.task_id)

    def __put_task_in_tasks_to_pay(self, task_id):
        task = self.computing_tasks.get(task_id)
        if task is None:
            logger.error("No information about payments for task {}".format(task_id))
            return
        self.tasks_to_pay.append(task)
        del self.computing_tasks[task_id]

    @staticmethod
    def __get_nodes_grouping(subtasks):
        nodes = {}
        for subtask in subtasks.itervalues():
            if subtask.computer.key_id in nodes:
                nodes[subtask.computer.key_id] += subtask.value
            else:
                nodes[subtask.computer.key_id] = subtask.value
        return nodes

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
            return self.__dict__ == other.__dict__
        return False
