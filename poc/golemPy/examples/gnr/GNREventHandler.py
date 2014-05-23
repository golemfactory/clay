
from PyQt4 import QtCore

class GNREventHandler:
    ##########################
    def __init__( self, ui, app ):
        self.ui     = ui
        self.app    = app
        self.__setupConnections()

    ##########################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.ui.showResourceButton, QtCore.SIGNAL( "clicked()" ), self.showResourceClicked )
        QtCore.QObject.connect( self.ui.actionNew, QtCore.SIGNAL( "triggered()" ), self.newTaskClicked )
        QtCore.QObject.connect( self.ui.renderTaskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.taskTableRowClicked )
        QtCore.QObject.connect( self.ui.renderTaskTableWidget, QtCore.SIGNAL( "customContextMenuRequested( const QPoint& )" ), self.contexMenuRequested )

    ##########################
    def showResourceClicked( self ):
        self.app.registerNewTask( "12231231", "dupa" )
        print "showResourceClicked"

    ##########################
    def newTaskClicked( self ):
        self.app.showNewTaskDialog()

    ##########################
    def taskTableRowClicked( self, row, column ):
        print "taskTableRowClicked {}".format( row )

    ##########################
    def contexMenuRequested( self, p ):
        item = self.ui.renderTaskTableWidget.itemAt( p )
        print "contexMenuRequested at row {}".format( item.row() ) 