import datetime

from PyQt4 import QtCore

from golem.task.TaskState import TaskState, ComputerState
from examples.gnr.TaskState import GNRTaskState

from examples.gnr.ui.SubtaskTableEntry import SubtaskTableElem

class TaskDetailsDialogCustomizer:
    ###########################
    def __init__( self, gui, logic, gnrTaskState ):
        assert isinstance( gnrTaskState, GNRTaskState )
        self.gui            = gui
        self.logic          = logic
        self.gnrTaskState   = gnrTaskState

        self.subtaskTableElements = {}

        self.__setupConnections()

        self.updateView( self.gnrTaskState.taskState )

    ###########################
    def updateView( self, taskState ):
        self.gnrTaskState.taskState = taskState
        self.__updateData()

    ###########################
    def __updateData( self ):
        self.gui.ui.totalTaskProgressBar.setProperty( "value", int( self.gnrTaskState.taskState.progress * 100 ) )
        self.gui.ui.estimatedRemainingTimeLabel.setText( str( datetime.timedelta( seconds = self.gnrTaskState.taskState.remainingTime ) ) )
        self.gui.ui.elapsedTimeLabel.setText( str( datetime.timedelta( seconds = self.gnrTaskState.taskState.elapsedTime ) ) )

        for k in self.gnrTaskState.taskState.subtaskStates:
            if k not in self.subtaskTableElements:
                ss = self.gnrTaskState.taskState.subtaskStates[ k ]
                self.__addNode( ss.computer.nodeId, ss.subtaskId, ss.subtaskStatus )

        for k in self.subtaskTableElements:
            elem = self.subtaskTableElements[ k ]
            ss = self.gnrTaskState.taskState.subtaskStates[ elem.subtaskId ]
            elem.update( ss.subtaskProgress, ss.subtaskStatus, ss.subtaskRemTime )

    ###########################
    def __setupConnections( self ):
        QtCore.QObject.connect( self.gui.ui.nodesTableWidget, QtCore.SIGNAL( "cellClicked(int, int)" ), self.__nodesTabelRowClicked )
        self.gui.ui.closeButton.clicked.connect( self.__closeButtonClicked )

    # ###########################
    # def __initializeData( self ):
    #     self.gui.ui.totalTaskProgressBar.setProperty( "value", int( self.gnrTaskState.taskState.progress * 100 ) )
    #     self.gui.ui.estimatedRemainingTimeLabel.setText( str( datetime.timedelta( seconds = self.gnrTaskState.taskState.remainingTime ) ) )
    #     self.gui.ui.elapsedTimeLabel.setText( str( datetime.timedelta( seconds = self.gnrTaskState.taskState.elapsedTime ) ) )
    #     for k in self.gnrTaskState.taskState.subtaskStates:
    #         if k not in self.subtaskTableElements:
    #             ss = self.gnrTaskState.taskState.subtaskStates[ k ]
    #             self.__addNode( ss.computer.nodeId, ss.subtaskId, ss.subtaskStatus )

    ###########################
    def __updateNodeAdditionalInfo( self, nodeId, subtaskId ):
        if subtaskId in self.gnrTaskState.taskState.subtaskStates:
            ss = self.gnrTaskState.taskState.subtaskStates[ subtaskId ]
            comp = ss.computer


            assert isinstance( comp, ComputerState )

            self.gui.ui.nodeIdLabel.setText( nodeId )
            self.gui.ui.nodeIpAddressLabel.setText( comp.ipAddress )
            self.gui.ui.performanceLabel.setText( "{} rays per sec".format( comp.performance ) )
            self.gui.ui.subtaskDefinitionTextEdit.setPlainText( ss.subtaskDefinition )

    ############################
    def __addNode( self, nodeId, subtaskId, status ):
        currentRowCount = self.gui.ui.nodesTableWidget.rowCount()
        self.gui.ui.nodesTableWidget.insertRow( currentRowCount )

        subtaskTableElem = SubtaskTableElem( nodeId, subtaskId, status )

        for col in range( 0, 4 ): self.gui.ui.nodesTableWidget.setItem( currentRowCount, col, subtaskTableElem.getColumnItem( col ) )

        self.gui.ui.nodesTableWidget.setCellWidget( currentRowCount, 4, subtaskTableElem.progressBarInBoxLayoutWidget )

        self.subtaskTableElements[ subtaskId ] = subtaskTableElem

        subtaskTableElem.update( 0.0, "", 0.0 )

        self.__updateNodeAdditionalInfo( nodeId, subtaskId )

    # SLOTS
    ###########################
    def __nodesTabelRowClicked( self, r, c ):

        nodeId = "{}".format( self.gui.ui.nodesTableWidget.item( r, 0 ).text() )
        subtaskId = "{}".format( self.gui.ui.nodesTableWidget.item( r, 1 ).text() )
        self.__updateNodeAdditionalInfo( nodeId, subtaskId )

    ###########################
    def __closeButtonClicked( self ):
        self.gui.window.close()
