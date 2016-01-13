from PyQt4.QtGui import QDialog
from gen.ui_EnvironmentsDialog import Ui_EnvironmentsDialog


class EnvironmentsDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_EnvironmentsDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()

    ###################
    def close(self):
        self.window.close()
