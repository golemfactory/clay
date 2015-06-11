from PaymentsKeeper import AccountInfo, PaymentsKeeper

################################################################
class EthereumPaymentsKeeper(PaymentsKeeper):
    ################################
    def getListOfPayments(self, task):
        payments = {}
        for subtask in task.subtasks.itervalues():
            payment = payments.setdefault(subtask.computer.ethAccount, EthereumPaymentInfo())
            payment.addSubtaskPayment(subtask)
        return payments

################################################################
class EthereumPaymentInfo:
    ################################
    def __init__(self):
        self.value = 0
        self.accounts = []
        self.accountsPayments = []

    ################################
    def addSubtaskPayment(self, subtask):
        self.value += subtask.value
        if subtask.computer in self.accounts:
            idx = self.accounts.index(subtask.computer)
            self.accountsPayments[idx] += subtask.value
        else:
            self.accounts.append(subtask.computer)
            self.accountsPayments.append(subtask.value)

################################################################
class EthAccountInfo(AccountInfo):
    ################################
    def __init__(self, keyId, port, addr, nodeId, ethAccount):
        AccountInfo.__init__(self, keyId, port, addr, nodeId)
        self.ethAccount = ethAccount

