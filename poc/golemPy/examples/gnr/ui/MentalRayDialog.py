from PyQt4.QtGui import QDialog
from gen.ui_MentalRayDialog import Ui_MentalRayDialog

class MentalRayDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_MentalRayDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
