from PyQt4.QtGui import QDialog
from gen.ui_ThreeDSMaxDialog import Ui_ThreeDSMaxDialog

class ThreeDSMaxDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_ThreeDSMaxDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
