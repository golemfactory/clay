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

        self.__setupConnections()

    ##########################
    def show( self ):
        self.window.show()

    ##########################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.ui.showResourceButton, QtCore.SIGNAL( "clicked()" ), self.__showResourceClicked )
        QtCore.QObject.connect( self.ui.renderTaskTableWidget, QtCore.SIGNAL( "customContextMenuRequested( const QPoint& )" ), self.__contexMenuRequested )

    # SLOTS
    ##########################
    def __showResourceClicked( self ):
        print "showResourceClicked"

    ##########################
    def __taskTableRowClicked( self, row, column ):
        self.emit( QtCore.SIGNAL( "taskTableRowClicked(int)" ), row)
        print "taskTableRowClicked {}".format( row )

    ##########################
    def __contexMenuRequested( self, p ):
        item = self.ui.renderTaskTableWidget.itemAt( p )
        print "contexMenuRequested at row {}".format( item.row() )