from os import urandom

from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.transactionsystem import TransactionSystem
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo
from golem.network.p2p.node import Node


class TestTransactionSystem(TestWithDatabase):
    def test_add_payment_info(self):
        e = TransactionSystem()
        ai = EthAccountInfo("DEF", 2010, "10.0.0.1", "node1", Node(), urandom(20))
        e.add_payment_info("xyz", "xxyyzz", 10, ai)

    def test_get_income(self):
        e = TransactionSystem()
        transaction_details = {
            'sender_node_id': 'senderid',
            'task_id': 'task_id',
            'subtask_id': 'subtask_id',
            'value': 100,
        }
        e.incomes_keeper.expect(**transaction_details)
        transaction_details['transaction_id'] = 'transaction_id'
