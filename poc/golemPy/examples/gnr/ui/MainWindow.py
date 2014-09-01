from PyQt4.QtGui import QMainWindow, QPixmap, QMessageBox

from gen.ui_MainWindow import Ui_MainWindow

class MainWindow( QMainWindow ):

    def closeEvent( self, event ):
        print("event")
        reply = QMessageBox.question(self, 'Golem Message',
            "Are you sure you want to quit?", QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

class GNRMainWindow:
    ##########################
    def __init__( self ):
        self.window     = MainWindow()
        self.ui         = Ui_MainWindow()

        self.ui.setupUi( self.window )
        self.ui.previewLabel.setPixmap( QPixmap( "ui/nopreview.jpg" ) )

    ##########################
    def show( self ):
        self.window.show()

