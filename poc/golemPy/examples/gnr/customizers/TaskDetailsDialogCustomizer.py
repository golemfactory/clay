import datetime

from PyQt4 import QtCore

from golem.task.TaskState import TaskState, ComputerState
from examples.gnr.TaskState import GNRTaskState

from ui.SubtaskTableEntry import SubtaskTableElem

class TaskDetailsDialogCustomizer:
    ###########################
    def __init__( self, gui, logic, taskState ):
        assert isinstance( taskState, GNRTaskState )
        self.gui        = gui
        self.logic      = logic
        self.taskState  = taskState

        self.__setupConnections()

        self.__initializeData() 

    ###########################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.gui.ui.nodesTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__nodesTabelRowClicked )
        self.gui.ui.closeButton.clicked.connect( self.__closeButtonClicked )

    ###########################
    def __initializeData( self ):
        self.gui.ui.totalTaskProgressBar.setProperty( "value", int( self.taskState.taskState.progress * 100 ) )
        self.gui.ui.estimatedRemainingTimeLabel.setText( str( datetime.timedelta( seconds = self.taskState.taskState.remainingTime ) ) )
        self.gui.ui.elapsedTimeLabel.setText( str( datetime.timedelta( seconds = self.taskState.taskState.elapsedTime ) ) )
        for ck in self.taskState.taskState.computers:
            self.__addNode( ck.nodeId, ck.subtaskState.subtaskId, ck.subtaskState.subtaskStatus )

    ###########################
    def __updateNodeAdditionalInfo( self, nodeId, subtaskId ):
        comp = None
        for c in self.taskState.taskState.computers:
            if c.nodeId == nodeId and c.subtaskState.subtaskId == subtaskId:
                comp = c
                break

        if not comp:
            comp = self.taskState.taskState.computers[ 0 ]

        assert isinstance( comp, ComputerState )

        self.gui.ui.nodeIdLabel.setText( nodeId )
        self.gui.ui.nodeIpAddressLabel.setText( comp.ipAddress )
        self.gui.ui.performanceLabel.setText( "{} rays per sec".format( comp.performance ) )
        self.gui.ui.subtaskDefinitionTextEdit.setPlainText( comp.subtaskState.subtaskDefinition )

    ############################
    def __addNode( self, nodeId, subtaskId, status ):
        currentRowCount = self.gui.ui.nodesTableWidget.rowCount()
        self.gui.ui.nodesTableWidget.insertRow( currentRowCount )

        subtaskTableElem = SubtaskTableElem( nodeId, subtaskId, status )

        for col in range( 0, 4 ): self.gui.ui.nodesTableWidget.setItem( currentRowCount, col, subtaskTableElem.getColumnItem( col ) )

        self.gui.ui.nodesTableWidget.setCellWidget( currentRowCount, 4, subtaskTableElem.progressBarInBoxLayoutWidget )

        self.__updateNodeAdditionalInfo( nodeId, subtaskId )

    # SLOTS
    ###########################
    def __nodesTabelRowClicked( self, r, c ):

        nodeId = "{}".format( self.gui.ui.nodesTableWidget.itemAt( r, 0 ).text() )
        subTaskId = "{}".format( self.gui.ui.nodesTableWidget.itemAt( r, 1 ).text() )
        self.__updateNodeAdditionalInfo( nodeId, subTaskId )

    ###########################
    def __closeButtonClicked( self ):
        self.gui.window.close()
