import sys
from PyQt4.QtGui import QApplication
from MainWindow import GNRMainWindow

class GNRGui:
    ############################
    def __init__( self ):
        self.app            = QApplication( sys.argv )
        self.mainWindow     = GNRMainWindow()

    ############################
    def execute( self ):
        self.mainWindow.show()
        sys.exit( self.app.exec_() )





