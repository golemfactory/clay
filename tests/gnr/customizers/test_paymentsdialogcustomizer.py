import unittest
from gnr.customizers.paymentsdialogcustomizer import PaymentTableElem, IncomeTableElem
from PyQt4.QtGui import QTableWidgetItem


class TestTableElem(unittest.TestCase):
    def test_payment_table_elem(self):
        a = PaymentTableElem({"state": "STATE1", "node": "a1234-123", "task": "ABC", "value": 209})
        for i in range(len(a.cols)):
            self.assertIsInstance(a.get_column_item(i), QTableWidgetItem)
        self.assertEqual(a.get_column_item(0).text(), "ABC")
        self.assertEqual(a.get_column_item(1).text(), "a1234-123")
        self.assertEqual(a.get_column_item(2).text(), "STATE1")
        self.assertEqual(a.get_column_item(3).text(), "209")

    def test_income_table_elem(self):
        b = IncomeTableElem({"state": "STATE2", "expected_value": 20, "node": "xyz123", "task": "ABB", "value": 0})
        for i in range(len(b.cols)):
            self.assertIsInstance(b.get_column_item(i), QTableWidgetItem)
        self.assertEqual(b.get_column_item(0).text(), "ABB")
        self.assertEqual(b.get_column_item(1).text(), "xyz123")
        self.assertEqual(b.get_column_item(2).text(), "STATE2")
        self.assertEqual(b.get_column_item(3).text(), "0")
        self.assertEqual(b.get_column_item(4).text(), "20")
