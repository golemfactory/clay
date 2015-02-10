from PyQt4.QtGui import QDialog
from gen.ui_BlenderRenderDialog import Ui_BlenderRenderDialog

class BlenderRenderDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_BlenderRenderDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
