from PyQt4.QtGui import QDialog
from gen.ui_VRayDialog import Ui_VRayDialog

class VRayDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_VRayDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
