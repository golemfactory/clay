
from PyQt4 import QtCore
from PyQt4.QtGui import QDialog
from gen.ui_TaskDetailsDialog import Ui_TaskDetailsDialog

class TaskDetailsDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_TaskDetailsDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()