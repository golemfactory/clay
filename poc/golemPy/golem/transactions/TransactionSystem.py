import logging
import datetime

from EthereumPaymentsKeeper import EthereumPaymentsKeeper
from PaymentsKeeper import PaymentInfo
from golem.Model import Bank

logger = logging.getLogger(__name__)

####################################################################################
class TransactionSystem:
    ############################
    def __init__(self, nodeId):
        self.nodeId = nodeId
        self.paymentsKeeper = EthereumPaymentsKeeper()
        self.budget = Bank.get(Bank.nodeId == nodeId).val
        self.priceBase = 10.0

    ############################
    def taskRewardPaid(self, taskId, price):
        Bank.update(val = self.budget, modified_date = str(datetime.datetime.now())).where(Bank.nodeId == self.nodeId).execute()

    ############################
    def taskRewardPaymentFailure(self, taskId, price):
        self.budget += price
        self.paymentsKeeper.paymentFailure(taskId)

    ################################
    def getReward(self, reward):
        self.budget += reward
        Bank.update(val = self.budget,  modified_date = str(datetime.datetime.now())).where(Bank.nodeId == self.nodeId).execute()

    ################################
    def addPaymentInfo(self, taskId, subtaskId, priceMod, accountInfo):
        price = self.countPrice(priceMod)
        paymentInfo = PaymentInfo(taskId, subtaskId, price, accountInfo)
        self.paymentsKeeper.addPayment(paymentInfo)

    ################################
    def taskFinished(self, taskId):
        self.paymentsKeeper.taskFinished(taskId)

    ################################
    def getNewPaymentsTasks(self):
        task, payments =  self.paymentsKeeper.getNewPaymentsTask(self.budget)
        if task is None:
            return None, None
        if self.budget >= task.value:
            self.budget -= task.value
            return task.taskId, payments
        else:
            self.paymentsKeeper.paymentFailure(task.taskId)
            logger.warning("Can't paid for the task, not enough money")
            return None, None

    ################################
    def countPrice(self, priceMod):
        return int(round(priceMod * self.priceBase))