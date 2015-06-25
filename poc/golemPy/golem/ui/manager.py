from PyQt4.QtGui import QDialog
from gen.ui_manager import Ui_NodesManagerWidget

class NodesManagerWidget:
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_NodesManagerWidget()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()