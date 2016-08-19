from __future__ import division

from gnr.customizers.customizer import Customizer
from PyQt4.QtGui import QTableWidgetItem
from twisted.internet.defer import inlineCallbacks
from ethereum.utils import denoms


class PaymentsDialogCustomizer(Customizer):

    @inlineCallbacks
    def load_data(self):
        payments = yield self.logic.get_payments()
        for payment in payments:
            self._add_payment(payment)
        incomes = yield self.logic.get_incomes()
        for income in incomes:
            self._add_income(income)

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.window.close)

    def _add_payment(self, payment_info):
        current_row_count = self.gui.ui.paymentsTable.rowCount()
        self.gui.ui.paymentsTable.insertRow(current_row_count)
        payment_table_elem = PaymentTableElem(payment_info)
        for col in range(len(payment_table_elem.cols)):
            self.gui.ui.paymentsTable.setItem(current_row_count, col, payment_table_elem.get_column_item(col))

    def _add_income(self, income_info):
        current_row_count = self.gui.ui.incomesTable.rowCount()
        self.gui.ui.incomesTable.insertRow(current_row_count)
        income_table_elem = IncomeTableElem(income_info)
        for col in range(len(income_table_elem.cols)):
            self.gui.ui.incomesTable.setItem(current_row_count, col, income_table_elem.get_column_item(col))

class SmartTableItem(QTableWidgetItem):
    def __lt__(self, other):
        t1 = self.text()
        t2 = other.text()
        if t1 is None:
            return True
        if t2 is None:
            return False
        t1 = str(t1)
        t2 = str(t2)
        if t1.endswith("ETH"):
            t1 = t1[:-4]
            t2 = t2[:-4]
            if len(t1) == 0:
                t1 = "0.0"
            if len(t2) == 0:
                t2 = "0.0"
            return float(t1) < float(t2)
        if t1.endswith("%"):
            t1 = t1[:-1]
            t2 = t2[:-1]
            if len(t1) == 0:
                t1 = "0.0"
            if len(t2) == 0:
                t2 = "0.0"
            return float(t1) < float(t2)
        return t1 < t2
            
            

class PaymentTableElem(object):
    def __init__(self, payment_info):
        fee = payment_info["fee"]
        value = payment_info["value"]
        fee = "{:.1f}%".format(float(fee * 100) / value) if fee else ""

        subtask = SmartTableItem(payment_info["subtask"])
        payee = SmartTableItem(payment_info["payee"].encode('hex'))
        value = SmartTableItem("{:.6f} ETH".format(value / denoms.ether))
        status = SmartTableItem(str(payment_info["status"]).replace("PaymentStatus.", ""))
        fee = SmartTableItem(fee)
        self.cols = [subtask, payee, status, value, fee]

    def get_column_item(self, col):
        return self.cols[col]


class IncomeTableElem(object):
    def __init__(self, income_info):
        value = income_info["value"]
        payer = SmartTableItem(income_info["payer"].encode('hex'))
        status = SmartTableItem(str(income_info["status"]).replace("PaymentStatus.", ""))
        value = SmartTableItem("{:.6f} ETH".format(value / denoms.ether))
        block_number = SmartTableItem(str(income_info["block_number"]))
        self.cols = [payer, status, value, block_number]

    def get_column_item(self, col):
        return self.cols[col]
