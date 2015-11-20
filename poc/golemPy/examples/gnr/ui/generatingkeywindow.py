from PyQt4.QtGui import QDialog
from gen.ui_GeneratingKeyWindow import Ui_generating_key_window


class GeneratingKeyWindow:
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_generating_key_window()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()

    def close(self):
        self.window.close()