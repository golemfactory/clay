from os import urandom
from unittest.mock import Mock, patch

from golem.model import Income
from golem.network.p2p.node import Node
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo
from golem.transactions.transactionsystem import TransactionSystem


class TestTransactionSystem(TestWithDatabase):
    def setUp(self):
        super(TestTransactionSystem, self).setUp()
        self.transaction_system = TransactionSystem()

    def test_add_payment_info(self):
        ai = EthAccountInfo("DEF", "node1", Node(), urandom(20))
        self.transaction_system.add_payment_info("xyz", "xxyyzz", 10, ai)

    def test_check_payments(self):
        with patch.object(
            self.transaction_system.incomes_keeper, 'update_overdue_incomes'
        ) as incomes:
            incomes.return_value = [
                Mock(spec=Income, sender_node='a'),
                Mock(spec=Income, sender_node='b')
            ]
            self.assertEqual(
                self.transaction_system.get_nodes_with_overdue_payments(),
                ['a', 'b']
            )
