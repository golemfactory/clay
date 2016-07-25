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


class PaymentTableElem(object):
    def __init__(self, payment_info):
        fee = payment_info["fee"]
        value = payment_info["value"]
        fee = "{:.1f}%".format(float(fee * 100) / value) if fee else ""

        subtask = QTableWidgetItem(payment_info["subtask"])
        payee = QTableWidgetItem(payment_info["payee"].encode('hex'))
        value = QTableWidgetItem("{:.6f} ETH".format(value / denoms.ether))
        status = QTableWidgetItem(str(payment_info["status"]).replace("PaymentStatus.", ""))
        fee = QTableWidgetItem(fee)
        self.cols = [subtask, payee, status, value, fee]

    def get_column_item(self, col):
        return self.cols[col]


class IncomeTableElem(object):
    def __init__(self, income_info):
        value = income_info["value"]
        payer = QTableWidgetItem(income_info["payer"].encode('hex'))
        status = QTableWidgetItem(str(income_info["status"]).replace("PaymentStatus.", ""))
        value = QTableWidgetItem("{:.6f} ETH".format(value / denoms.ether))
        block_number = QTableWidgetItem(str(income_info["block_number"]))
        self.cols = [payer, status, value, block_number]

    def get_column_item(self, col):
        return self.cols[col]
