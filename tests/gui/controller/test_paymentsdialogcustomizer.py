import unittest

from PyQt5.QtWidgets import QTableWidgetItem

from golem.model import PaymentStatus

from gui.controller.paymentsdialogcustomizer import PaymentTableElem, IncomeTableElem, SmartTableItem


class TestTableElem(unittest.TestCase):
    def test_payment_table_elem(self):
        ethereum_address_hex = "aabbccddeeffaabbccddeeffaabbccddeeff0011"
        a = PaymentTableElem({u"status": unicode(PaymentStatus.awaiting.name),
                              u"payee": unicode(ethereum_address_hex),
                              u"subtask": u"ABC",
                              u"value": unicode(209*10**15),
                              u"fee": None})
        for i in range(len(a.cols)):
            self.assertIsInstance(a.get_column_item(i), QTableWidgetItem)
        self.assertEqual(a.get_column_item(0).text(), u"ABC")
        self.assertEqual(a.get_column_item(1).text(), ethereum_address_hex)
        self.assertEqual(a.get_column_item(2).text(), u"awaiting")
        self.assertEqual(a.get_column_item(3).text(), u"0.209000 ETH")

    def test_income_table_elem(self):
        ethereum_address_hex = "ffbbccddeeffaabbccddeeffaabbccddeeff0088"
        b = IncomeTableElem({u"status": unicode(PaymentStatus.confirmed.name),
                             u"value": unicode(211 * 10**16),
                             u"payer": unicode(ethereum_address_hex),
                             u"block_number": u"ABB"})
        for i in range(len(b.cols)):
            self.assertIsInstance(b.get_column_item(i), QTableWidgetItem)
        self.assertEqual(b.get_column_item(0).text(), ethereum_address_hex)
        self.assertEqual(b.get_column_item(1).text(), "confirmed")
        self.assertEqual(b.get_column_item(2).text(), "2.110000 ETH")
        self.assertEqual(b.get_column_item(3).text(), "ABB")


class TestSmartTableItem(unittest.TestCase):
    def test_comparison(self):
        i1 = SmartTableItem("11121")
        i2 = SmartTableItem("111111")
        self.assertTrue(i2 < i1)
        
        i1 = SmartTableItem("aa11121")
        i2 = SmartTableItem("a111111")
        self.assertTrue(i2 < i1)
        
        i1 = SmartTableItem("0%")
        i2 = SmartTableItem("0.001%")
        self.assertTrue(i1 < i2)
        
        i1 = SmartTableItem("")
        i2 = SmartTableItem("0.001%")
        self.assertTrue(i1 < i2)
        
        i1 = SmartTableItem("0.01%")
        i2 = SmartTableItem("")
        self.assertTrue(i2 < i1)
        
        i1 = SmartTableItem("3.001%")
        i2 = SmartTableItem("0.001%")
        self.assertTrue(i2 < i1)
        
        i1 = SmartTableItem("0.0001 ETH")
        i2 = SmartTableItem("0.001 ETH")
        self.assertTrue(i1 < i2)
        
        i1 = SmartTableItem("123 ETH")
        i2 = SmartTableItem("0.0001 ETH")
        self.assertTrue(i2 < i1)
        
        i1 = SmartTableItem("")
        i2 = SmartTableItem("0.001 ETH")
        self.assertTrue(i1 < i2)
        
        i1 = SmartTableItem("123 ETH")
        i2 = SmartTableItem("")
        self.assertTrue(i2 < i1)
        
        i1 = None
        self.assertTrue(i1 < i2)
        
        i1 = SmartTableItem("123 ETH")
        i2 = None
        self.assertTrue(i2 < i1)
