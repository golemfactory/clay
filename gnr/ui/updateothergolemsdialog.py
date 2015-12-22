from PyQt4.QtGui import QDialog
from gen.ui_UpdateOtherGolemsDialog import Ui_UpdateOtherGolemsDialog

class UpdateOtherGolemsDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_UpdateOtherGolemsDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()

    ###################
    def close(self):
        self.window.close()
