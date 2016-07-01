from gnr.customizers.customizer import Customizer
from PyQt4.QtGui import QTableWidgetItem


class PaymentsDialogCustomizer(Customizer):

    def load_data(self):
        payments = self.logic.get_payments()
        for payment in payments:
            self._add_payment(payment)
        incomes = self.logic.get_incomes()
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
        self.task = payment_info["task"]
        self.node = payment_info["node"]
        self.value = payment_info["value"]
        self.state = payment_info["state"]
        self.cols = []
        self._build_row()

    def _build_row(self):
        self.task_item = QTableWidgetItem()
        self.task_item.setText(self.task)

        self.node_item = QTableWidgetItem()
        self.node_item.setText(self.node.encode('hex'))

        self.value_item = QTableWidgetItem()
        self.value_item.setText("{:f} ETH".format(float(self.value) / 10**18))

        self.state_item = QTableWidgetItem()
        self.state_item.setText(str(self.state).replace("PaymentStatus.", ""))

        self.cols = [self.task_item, self.node_item, self.state_item, self.value_item]

    def get_column_item(self, col):
        return self.cols[col]


class IncomeTableElem(PaymentTableElem):
    def __init__(self, income_info):
        self.expected_value = income_info["expected_value"]
        PaymentTableElem.__init__(self, income_info)

    def _build_row(self):
        PaymentTableElem._build_row(self)
        self.expected_value_item = QTableWidgetItem()
        self.expected_value_item.setText(str(self.expected_value))
        self.cols += [self.expected_value_item]
