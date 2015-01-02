import sys
from PyQt4.QtGui import QApplication

class GNRGui:
    ############################
    def __init__( self, appLogic, mainWindowClass ):
        self.app            = QApplication( sys.argv )
        self.mainWindow     = mainWindowClass()
        self.appLogic       = appLogic

    ############################
    def execute( self, usingqt4Reactor = True ):
        self.mainWindow.show()
        if not usingqt4Reactor:
            sys.exit( self.app.exec_() )

    ############################
    def getMainWindow( self ):
        return self.mainWindow





