from golem.transactions.TransactionSystem import TransactionSystem
from EthereumConnector import EthereumConnector

from golem.core.variables import ETH_CONN_ADDR

####################################################################################
class EthereumTransactionSystem(TransactionSystem):
    ############################
    def __init__(self, nodeId, eth_account):
        TransactionSystem.__init__(self, nodeId)
        self.eth_account = eth_account

    ############################
    def global_pay_for_task(self, taskId, payments):
        ethConnector = EthereumConnector(ETH_CONN_ADDR)
        ethConnector.payForTask(self.eth_account, taskId, payments)