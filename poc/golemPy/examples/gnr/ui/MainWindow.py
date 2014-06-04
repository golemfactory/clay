from PyQt4 import QtCore
from PyQt4.QtGui import QMainWindow, QPixmap

from gen.ui_MainWindow import Ui_MainWindow

from NewTaskDialog import NewTaskDialog

class GNRMainWindow:
    ##########################
    def __init__( self ):
        self.window     = QMainWindow()
        self.ui         = Ui_MainWindow()

        self.ui.setupUi( self.window )
        self.ui.previewLabel.setPixmap( QPixmap( "ui/nopreview.jpg" ) )

    ##########################
    def show( self ):
        self.window.show()

