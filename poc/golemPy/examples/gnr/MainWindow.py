from PyQt4 import QtCore
from PyQt4.QtGui import QMainWindow, QPixmap

from ui_MainWindow import Ui_MainWindow

from GNREventHandler import GNREventHandler
from TaskTableElem import TaskTableElem
from NewTaskDialog import NewTaskDialog

class GNRMainWindow:
    ##########################
    def __init__( self ):
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
        QtCore.QObject.connect( self.ui.actionNew, QtCore.SIGNAL( "triggered()" ), self.__newTaskClicked )
        QtCore.QObject.connect( self.ui.renderTaskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__taskTableRowClicked )
        QtCore.QObject.connect( self.ui.renderTaskTableWidget, QtCore.SIGNAL( "customContextMenuRequested( const QPoint& )" ), self.__contexMenuRequested )

    ############################
    def registerNewTask( self, id, status ):
        currentRowCount = self.ui.renderTaskTableWidget.rowCount()
        self.ui.renderTaskTableWidget.insertRow( currentRowCount )

        taskTableElem = TaskTableElem( id, status )

        for col in range( 0, 2 ): self.ui.renderTaskTableWidget.setItem( currentRowCount, col, taskTableElem.getColumnItem( col ) )

        self.ui.renderTaskTableWidget.setCellWidget( currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget )

    ############################
    def showNewTaskDialog( self ):
        self.newTaskDialog = NewTaskDialog( self.window )
        self.newTaskDialog.show()

    # SLOTS
    ##########################
    def __showResourceClicked( self ):
        self.registerNewTask( "12231231", "dupa" )

    ##########################
    def __newTaskClicked( self ):
        self.showNewTaskDialog()

    ##########################
    def __taskTableRowClicked( self, row, column ):
        print "taskTableRowClicked {}".format( row )

    ##########################
    def __contexMenuRequested( self, p ):
        item = self.ui.renderTaskTableWidget.itemAt( p )
        print "contexMenuRequested at row {}".format( item.row() ) 