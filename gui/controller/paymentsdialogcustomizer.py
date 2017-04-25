from __future__ import division

from golem.model import PaymentStatus
from gui.controller.customizer import Customizer
from PyQt5.QtWidgets import QTableWidgetItem
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
        t1 = str(self.text())
        t2 = str(other.text())
        for postfix in ['ETH', '%']:
            if t1.endswith(postfix) or t2.endswith(postfix):
                l = len(postfix)
                t1 = self.to_float(t1[:-l])
                t2 = self.to_float(t2[:-l])
                return t1 < t2
        return t1 < t2

    @staticmethod
    def to_float(t):
        try:
            return float(t)
        except Exception:
            return 0.0


class PaymentTableElem(object):
    def __init__(self, payment_info):
        fee = payment_info["fee"]
        value = float(payment_info["value"])
        fee = "{:.1f}%".format(float(fee) * 100 / value) if fee else ""
        payment_status = PaymentStatus(payment_info["status"])

        subtask = SmartTableItem(payment_info["subtask"])
        payee = SmartTableItem(payment_info["payee"].encode('hex'))
        value = SmartTableItem("{:.6f} ETH".format(value / denoms.ether))
        status = SmartTableItem(str(payment_status).replace("PaymentStatus.", ""))
        fee = SmartTableItem(fee)
        self.cols = [subtask, payee, status, value, fee]

    def get_column_item(self, col):
        return self.cols[col]


class IncomeTableElem(object):
    def __init__(self, income_info):
        payment_status = PaymentStatus(income_info["status"])
        value = float(income_info["value"])
        payer = SmartTableItem(income_info["payer"].encode('hex'))
        status = SmartTableItem(str(payment_status).replace("PaymentStatus.", ""))
        value = SmartTableItem("{:.6f} ETH".format(value / denoms.ether))
        block_number = SmartTableItem(str(income_info["block_number"]))
        self.cols = [payer, status, value, block_number]

    def get_column_item(self, col):
        return self.cols[col]
