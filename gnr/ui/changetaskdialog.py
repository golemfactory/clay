from PyQt4.QtGui import QDialog
from gen.ui_ChangeTaskDialog import Ui_ChangeTaskDialog


class ChangeTaskDialog:
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_ChangeTaskDialog()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()
