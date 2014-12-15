from PyQt4.QtGui import QDialog
from examples.default.ui.gen.ui_NewTaskDialog import Ui_NewTaskDialog

class NewTaskDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_NewTaskDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
