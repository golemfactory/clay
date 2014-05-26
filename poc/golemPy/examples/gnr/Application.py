import sys
from PyQt4.QtGui import QApplication
from MainWindow import GNRMainWindow

class GNRGui:
    ############################
    def __init__( self, appLogic ):
        self.app            = QApplication( sys.argv )
        self.mainWindow     = GNRMainWindow()
        self.appLogic       = appLogic

    ############################
    def execute( self ):
        self.mainWindow.show()
        sys.exit( self.app.exec_() )

    ############################
    def getMainWindow( self ):
        return self.mainWindow





