from PyQt4.QtGui import QDialog
from gen.ui_PbrtDialog import Ui_PbrtDialog


class PbrtDialog:
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_PbrtDialog()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()
