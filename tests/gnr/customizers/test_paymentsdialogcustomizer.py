import unittest
from golem.model import PaymentStatus
from gnr.customizers.paymentsdialogcustomizer import PaymentTableElem, IncomeTableElem
from PyQt4.QtGui import QTableWidgetItem


class TestTableElem(unittest.TestCase):
    def test_payment_table_elem(self):
        ethereum_address_hex = "aabbccddeeffaabbccddeeffaabbccddeeff0011"
        ethereum_address = ethereum_address_hex.decode('hex')
        a = PaymentTableElem({"status": "STATE1", "payee": ethereum_address,
                              "subtask": "ABC", "value": 209*10**15,
                              "fee": None})
        for i in range(len(a.cols)):
            self.assertIsInstance(a.get_column_item(i), QTableWidgetItem)
        self.assertEqual(a.get_column_item(0).text(), "ABC")
        self.assertEqual(a.get_column_item(1).text(), ethereum_address_hex)
        self.assertEqual(a.get_column_item(2).text(), "STATE1")
        self.assertEqual(a.get_column_item(3).text(), "0.209000 ETH")

    def test_income_table_elem(self):
        ethereum_address_hex = "ffbbccddeeffaabbccddeeffaabbccddeeff0088"
        ethereum_address = ethereum_address_hex.decode('hex')
        b = IncomeTableElem({"status": PaymentStatus.confirmed, "value": 211 * 10**16,
                             "payer": ethereum_address, "block_number": "ABB"})
        for i in range(len(b.cols)):
            self.assertIsInstance(b.get_column_item(i), QTableWidgetItem)
        self.assertEqual(b.get_column_item(0).text(), ethereum_address_hex)
        self.assertEqual(b.get_column_item(1).text(), "confirmed")
        self.assertEqual(b.get_column_item(2).text(), "2.110000 ETH")
        self.assertEqual(b.get_column_item(3).text(), "ABB")

