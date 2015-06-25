from PyQt4.QtGui import QDialog
from gen.ui_StatusWindow import Ui_StatusWindow

class StatusWindow:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_StatusWindow()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()