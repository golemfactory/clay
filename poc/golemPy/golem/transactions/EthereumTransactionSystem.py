from TransactionSystem import TransactionSystem
from EthereumConnector import EthereumConnector

from golem.core.variables import ETH_CONN_ADDR

####################################################################################
class EthereumTransactionSystem(TransactionSystem):
    ############################
    def __init__(self, nodeId, ethAccount):
        TransactionSystem.__init__(self, nodeId)
        self.ethAccount = ethAccount

    ############################
    def globalPayForTask(self, taskId, payments):
        ethConnector = EthereumConnector(ETH_CONN_ADDR)
        ethConnector.payForTask(self.ethAccount, taskId, payments)