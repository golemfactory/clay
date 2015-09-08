from golem.transactions.PaymentsKeeper import AccountInfo, PaymentsKeeper

################################################################
class EthereumPaymentsKeeper(PaymentsKeeper):
    ################################
    def get_list_of_payments(self, task):
        payments = {}
        for subtask in task.subtasks.itervalues():
            payment = payments.setdefault(subtask.computer.eth_account, EthereumPaymentInfo())
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
    def __init__(self, key_id, port, addr, node_id, node_info, eth_account):
        AccountInfo.__init__(self, key_id, port, addr, node_id, node_info)
        self.eth_account = eth_account

