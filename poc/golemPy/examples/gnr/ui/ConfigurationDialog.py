from PyQt4.QtGui import QDialog
from gen.ui_ConfigurationDialog import Ui_ConfigurationDialog

class ConfigurationDialog:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_ConfigurationDialog()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()
