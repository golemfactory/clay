
from PyQt4 import QtCore

class GNREventHandler:
    ##########################
    def __init__( self, ui ):
        self.ui     = ui
        self.__setupConnections()

    ##########################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.ui.showResourceButton, QtCore.SIGNAL( "clicked()" ), self.showResourceClicked )
        QtCore.QObject.connect( self.ui.actionNew, QtCore.SIGNAL( "triggered()" ), self.newTaskClicked )
        QtCore.QObject.connect( self.ui.renderTaskTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.taskTableRowClicked )

    ##########################
    def showResourceClicked( self ):
        print "showResourceClicked"

    ##########################
    def newTaskClicked( self ):
        print "newTaskClicked"

    def taskTableRowClicked( self, row, column ):
        print "taskTableRowClicked {}".format( row )