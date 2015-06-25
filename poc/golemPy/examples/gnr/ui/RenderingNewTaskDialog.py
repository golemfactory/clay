from PyQt4.QtGui import QDialog
from gen.ui_RenderingNewTaskDialog import Ui_RenderingNewTaskDialog

class NewTaskDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_RenderingNewTaskDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()
