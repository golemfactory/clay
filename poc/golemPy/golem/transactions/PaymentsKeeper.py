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
    def taskFinished(self, taskId):
        self.finishedTasks.append(taskId)

    ###############################
    def paymentFailure(self, taskId):
        task = self.settledTasks.get(taskId)
        if task is None:
            logger.error("Unknown payment for task {}".format(taskId))
            return
        self.tasksToPay.append(task)
        del self.settledTasks[taskId]

    ################################
    def getNewPaymentsTask(self, budget):
        if len( self.tasksToPay ) > 0:
            task = self.tasksToPay.popleft()
            if task.value < budget:
                self.settledTasks[task.taskId] = task
                return task, self.getListOfPayments(task)
            else:
                self.tasksToPay.append(task)
        else:
            return None, None

    ################################
    def getListOfPayments(self, task):
        return task.subtasks

    ################################
    def addPayment(self, paymentInfo):
        task = self.computingTasks.setdefault(paymentInfo.taskId, TaskPaymentInfo(paymentInfo.taskId))
        task.subtasks[paymentInfo.subtaskId]  = SubtaskPaymentInfo(paymentInfo.value, paymentInfo.computer)
        task.value += paymentInfo.value
        if paymentInfo.taskId in self.finishedTasks:
            self.finishedTasks.remove(paymentInfo.taskId)
            self.__putTaskInTasksToPay(paymentInfo.taskId)

    ################################
    def __putTaskInTasksToPay(self, taskId):
        task = self.computingTasks.get(taskId)
        if task is None:
            logger.error("No information about payments for task {}".format(taskId))
            return
        self.tasksToPay.append(task)
        del self.computingTasks[taskId]


################################################################
class PaymentInfo:
    ################################
    def __init__(self, taskId, subtaskId, value, computer):
        self.taskId = taskId
        self.subtaskId = subtaskId
        self.value = value
        self.computer = computer

################################################################
class TaskPaymentInfo:
    ################################
    def __init__(self, taskId):
        self.taskId = taskId
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
    def __init__(self, keyId, port, addr, nodeId):
        self.keyId = keyId
        self.port = port
        self.addr = addr
        self.nodeId = nodeId

    ################################
    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False