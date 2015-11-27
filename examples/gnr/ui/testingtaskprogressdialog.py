from PyQt4.QtGui import QDialog
from gen.ui_TestingTaskProgressDialog import Ui_testingTaskProgressDialog


class TestingTaskProgressDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_testingTaskProgressDialog()
        self.ui.setupUi(self.window)
        self.ui.okButton.clicked.connect(self.close)

    def show(self):
        self.window.show()

    def close(self):
        self.window.close()

    def showMessage(self, mesg):
        self.ui.message.setText(mesg)
