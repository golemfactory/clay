from PyQt4.QtGui import QDialog
from gen.ui_IdentityDialog import Ui_identity_dialog


class IdentityDialog:
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_identity_dialog()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()