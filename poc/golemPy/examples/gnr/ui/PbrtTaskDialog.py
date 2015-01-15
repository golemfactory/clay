from PyQt4.QtGui import QDialog
from gen.ui_PbrtTaskDialog import Ui_PbrtTaskDialog

class PbrtTaskDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_PbrtTaskDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
