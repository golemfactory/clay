from os import urandom
from unittest.mock import Mock, patch

from eth_utils import encode_hex

from golem.model import Income
from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.transactionsystem import TransactionSystem


class TestTransactionSystem(TestWithDatabase):
    def setUp(self):
        super(TestTransactionSystem, self).setUp()
        self.transaction_system = TransactionSystem()

    def test_add_payment_info(self):
        self.transaction_system.add_payment_info(
            "xxyyzz",
            10,
            encode_hex(urandom(20)),
        )

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
            incomes.assert_called_once()
