from PyQt4 import QtCore
from PyQt4.QtGui import QDialog
from gen.ui_SubtaskDetailsDialog import Ui_SubtaskDetailsDialog

class SubtaskDetailsDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_SubtaskDetailsDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()