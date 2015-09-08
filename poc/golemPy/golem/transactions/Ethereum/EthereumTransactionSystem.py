from golem.transactions.transaction_system import TransactionSystem
from EthereumConnector import EthereumConnector

from golem.core.variables import ETH_CONN_ADDR

####################################################################################
class EthereumTransactionSystem(TransactionSystem):
    ############################
    def __init__(self, node_id, eth_account):
        TransactionSystem.__init__(self, node_id)
        self.eth_account = eth_account

    ############################
    def global_pay_for_task(self, task_id, payments):
        ethConnector = EthereumConnector(ETH_CONN_ADDR)
        ethConnector.payForTask(self.eth_account, task_id, payments)