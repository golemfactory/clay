import logging
from collections import deque


logger = logging.getLogger(__name__)

#################################################################
class PaymentsKeeper:
    ################################
    def __init__(self):
        self.computingTasks = {}
        self.finishedTasks = []
        self.tasksToPay = deque()
        self.waitingForPayments = {}
        self.settledTasks = {}

    ################################
    def task_finished(self, task_id):
        self.finishedTasks.append(task_id)

    ###############################
    def payment_failure(self, task_id):
        task = self.settledTasks.get(task_id)
        if task is None:
            logger.error("Unknown payment for task {}".format(task_id))
            return
        self.tasksToPay.append(task)
        del self.settledTasks[task_id]

    ################################
    def get_new_payments_task(self, budget):
        if len(self.tasksToPay) > 0:
            task = self.tasksToPay.popleft()
            if task.value < budget:
                self.settledTasks[task.task_id] = task
                return task, self.getListOfPayments(task)
            else:
                self.tasksToPay.append(task)
        else:
            return None, None

    ################################
    def getListOfPayments(self, task):
        return task.subtasks

    ################################
    def addPayment(self, payment_info):
        task = self.computingTasks.setdefault(payment_info.task_id, TaskPaymentInfo(payment_info.task_id))
        task.subtasks[payment_info.subtask_id]  = SubtaskPaymentInfo(payment_info.value, payment_info.computer)
        task.value += payment_info.value
        if payment_info.task_id in self.finishedTasks:
            self.finishedTasks.remove(payment_info.task_id)
            self.__putTaskInTasksToPay(payment_info.task_id)

    ################################
    def __putTaskInTasksToPay(self, task_id):
        task = self.computingTasks.get(task_id)
        if task is None:
            logger.error("No information about payments for task {}".format(task_id))
            return
        self.tasksToPay.append(task)
        del self.computingTasks[task_id]


################################################################
class PaymentInfo:
    ################################
    def __init__(self, task_id, subtask_id, value, computer):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.value = value
        self.computer = computer

################################################################
class TaskPaymentInfo:
    ################################
    def __init__(self, task_id):
        self.task_id = task_id
        self.subtasks = {}
        self.value = 0

################################################################
class SubtaskPaymentInfo:
    ################################
    def __init__(self, value, computer):
        self.value = value
        self.computer = computer

################################################################
class AccountInfo:
    ################################
    def __init__(self, keyId, port, addr, node_id, node_info):
        self.keyId = keyId
        self.port = port
        self.addr = addr
        self.node_id = node_id
        self.node_info = node_info

    ################################
    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False