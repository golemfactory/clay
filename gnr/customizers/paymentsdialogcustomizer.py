from gnr.customizers.customizer import Customizer
from PyQt4.QtGui import QTableWidgetItem


class PaymentsDialogCustomizer(Customizer):

    def load_data(self):
        payments = self.logic.get_payments()
        for payment in payments:
            self._add_payment(payment)

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.window.close)

    def _add_payment(self, payment_info):
        current_row_count = self.gui.ui.paymentsTable.rowCount()
        self.gui.ui.paymentsTable.insertRow(current_row_count)
        payment_table_elem = PaymentTableElem(payment_info)
        for col in range(len(payment_table_elem.cols)):
            self.gui.ui.paymentsTable.setItem(current_row_count, col, payment_table_elem.get_column_item(col))


class PaymentTableElem(object):
    def __init__(self, payment_info):
        print payment_info
        self.task = payment_info["task"]
        self.node = payment_info["node"]
        self.amount = payment_info["amount"]
        self.date = payment_info["date"]
        self.cols = []
        self.__build_row()

    def __build_row(self):
        self.task_item = QTableWidgetItem()
        self.task_item.setText(self.task)

        self.node_item = QTableWidgetItem()
        self.node_item.setText(self.node)

        self.amount_item = QTableWidgetItem()
        self.amount_item.setText(str(self.amount))

        self.date_item = QTableWidgetItem()
        self.date_item.setText(str(self.date))

        self.cols = [self.task_item, self.node_item, self.date_item, self.amount_item]

    def get_column_item(self, col):
        return self.cols[col]
