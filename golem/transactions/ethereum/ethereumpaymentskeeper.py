import logging
from rlp.utils import encode_hex

from ethereum.utils import normalize_address

from golem.transactions.paymentskeeper import AccountInfo, PaymentsKeeper

logger = logging.getLogger(__name__)


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
            payment = payments.setdefault(subtask.computer.eth_account.get_str_addr(), EthereumPaymentInfo())
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
        self.eth_account = EthereumAddress(eth_account)

    def __eq__(self, other):
        ethereum_eq = self.eth_account == other.eth_account
        account_eq = AccountInfo.__eq__(self, other)
        return ethereum_eq and account_eq


class EthereumAddress(object):
    """ Keeps information about ethereum addresses in normalized format
    """

    @classmethod
    def __parse(cls, address):
        if len(address) in range(40, 51):
            address = address.lower()
        return normalize_address(address)

    def __init__(self, address):
        self.address = None
        try:
            self.address = self.__parse(address)
        except Exception as err:
            logger.warning("Can't set Ethereum address, {} is not a proper value: {}".format(address, err))

    def get_str_addr(self):
        if self.address:
            return "0x{}".format(encode_hex(self.address))
        return None

    def __eq__(self, other):
        return self.address == other.address
