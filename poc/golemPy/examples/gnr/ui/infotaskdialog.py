from PyQt4.QtGui import QDialog
from gen.ui_InfoTaskDialog import Ui_InfoTaskDialog

class InfoTaskDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_InfoTaskDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()

    ###################
    def close(self):
        self.window.close()
