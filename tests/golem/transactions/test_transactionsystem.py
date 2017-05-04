from os import urandom

from golem.tools.testwithdatabase import TestWithDatabase
from golem.transactions.transactionsystem import TransactionSystem
from golem.transactions.ethereum.ethereumpaymentskeeper import EthAccountInfo
from golem.transactions.incomeskeeper import IncomesState
from golem.network.p2p.node import Node


class TestTransactionSystem(TestWithDatabase):
    def test_init(self):
        e = TransactionSystem()
        self.assertIsInstance(e, TransactionSystem)
        e.sync()  # nop

    def test_add_payment_info(self):
        e = TransactionSystem()
        ai = EthAccountInfo("DEF", 2010, "10.0.0.1", "node1", Node(), urandom(20))
        e.add_payment_info("xyz", "xxyyzz", 10, ai)

    def test_pay_for_task(self):
        e = TransactionSystem()
        with self.assertRaises(NotImplementedError):
            e.pay_for_task("xyz", [])

        iter(e.check_payments())

    def test_get_income(self):
        e = TransactionSystem()
        e.add_to_waiting_payments("xyz", "DEF", 15)
        income = e.get_incomes_list()[0]
        self.assertEqual(income["value"], 0)
        self.assertEqual(income["expected_value"], 15)
        self.assertEqual(income["state"], IncomesState.waiting)
        e.get_income("DEF", 10)
        income = e.get_incomes_list()[0]
        self.assertEqual(income["value"], 10)
        self.assertEqual(income["expected_value"], 15)
        self.assertEqual(income["state"], IncomesState.waiting)
        e.get_income("XYZ", 31)
        income = e.get_incomes_list()[0]
        self.assertEqual(income["value"], 10)
        self.assertEqual(income["expected_value"], 15)
        self.assertEqual(income["state"], IncomesState.waiting)
        e.get_income("DEF", 2)
        income = e.get_incomes_list()[0]
        self.assertEqual(income["value"], 12)
        self.assertEqual(income["expected_value"], 15)
        self.assertEqual(income["state"], IncomesState.waiting)
        e.get_income("DEF", 3)
        income = e.get_incomes_list()[0]
        self.assertEqual(income["value"], 15)
        self.assertEqual(income["expected_value"], 15)
        self.assertEqual(income["state"], IncomesState.finished)
