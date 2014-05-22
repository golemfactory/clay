
import sys
from PyQt4.QtGui import QApplication, QMainWindow
from ui_MainWindow import Ui_MainWindow
from GNREventHandler import GNREventHandler

class GNRGui:
    ############################
    def __init__( self ):
        self.app    = QApplication( sys.argv )
        self.window = QMainWindow()
        self.ui     = Ui_MainWindow()
        self.ui.setupUi( self.window )

        self.eventHandler = GNREventHandler( self.ui )

    ############################
    def execute( self ):
        self.window.show()
        sys.exit( self.app.exec_() )

