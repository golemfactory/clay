from PyQt4.QtGui import QDialog
from gen.ui_LuxRenderDialog import Ui_LuxRenderDialog

class LuxRenderDialog:
    ###################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_LuxRenderDialog()
        self.ui.setupUi(self.window)

    ###################
    def show(self):
        self.window.show()


    ###################
    def close(self):
        self.window.close()

