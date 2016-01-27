from golem.transactions.paymentskeeper import AccountInfo, PaymentsKeeper


class EthereumPaymentsKeeper(PaymentsKeeper):
    """ Keeps information about payments for tasks that should be processed and send or received via Ethereum. """
    def get_list_of_payments(self, task):
        """ Extract information about subtask payment from given task payment info. Group information by ethereum
        address
        :param EthereumPaymentInfo task: information about payments for a task
        :return dict: dictionary with information about subtask payments
        """
        payments = {}
        for subtask in task.subtasks.itervalues():
            payment = payments.setdefault(subtask.computer.eth_account, EthereumPaymentInfo())
            payment.add_subtask_payment(subtask)
        return payments


class EthereumPaymentInfo(object):
    """ Full information about payment for a subtask. Include task id, subtask payment information and
    account information about node that has computed this task. Group information by Ethereum account info. """
    def __init__(self):
        self.value = 0
        self.accounts = []
        self.accountsPayments = []

    def add_subtask_payment(self, subtask):
        """ Add information about payment for given subtask to this payment information
        :param SubtaskPaymentInfo subtask: information about payment for a subtask
        """
        self.value += subtask.value
        if subtask.computer in self.accounts:
            idx = self.accounts.index(subtask.computer)
            self.accountsPayments[idx] += subtask.value
        else:
            self.accounts.append(subtask.computer)
            self.accountsPayments.append(subtask.value)


class EthAccountInfo(AccountInfo):
    """ Information about node's payment account and Ethereum account. """
    def __init__(self, key_id, port, addr, node_name, node_info, eth_account):
        AccountInfo.__init__(self, key_id, port, addr, node_name, node_info)
        self.eth_account = eth_account

    def __eq__(self, other):
        ethereum_eq = self.eth_account == other.eth_account
        account_eq = AccountInfo.__eq__(self, other)
        return ethereum_eq and account_eq

