from PyQt4.QtGui import QDialog
from gen.ui_AboutWindow import Ui_AboutWindow

class AboutWindow:
    ###################
    def __init__( self, parent ):
        self.window = QDialog( parent )
        self.ui = Ui_AboutWindow()
        self.ui.setupUi( self.window )

    ###################
    def show( self ):
        self.window.show()