from PyQt4 import QtCore
from PyQt4.QtGui import QMainWindow, QPixmap

from ui_MainWindow import Ui_MainWindow

from NewTaskDialog import NewTaskDialog

class GNRMainWindow( QtCore.QObject ):
    ##########################
    def __init__( self ):
        QtCore.QObject.__init__( self )
        self.window     = QMainWindow()
        self.ui         = Ui_MainWindow()

        self.ui.setupUi( self.window )
        self.ui.previewLabel.setPixmap( QPixmap( "./../examples/gnr/ui/nopreview.jpg" ) )

    ##########################
    def show( self ):
        self.window.show()

