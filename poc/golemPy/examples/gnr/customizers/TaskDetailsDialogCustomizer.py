import datetime

from PyQt4 import QtCore

from TaskState import TaskState, ComputerState

from ui.SubtaskTableEntry import SubtaskTableElem

class TaskDetailsDialogCustomizer:
    ###########################
    def __init__( self, gui, logic, taskState ):
        assert isinstance( taskState, TaskState )
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
        self.gui.ui.totalTaskProgressBar.setProperty( "value", int( self.taskState.progress * 100 ) )
        self.gui.ui.estimatedRemainingTimeLabel.setText( str( datetime.timedelta( seconds = self.taskState.remainingTime ) ) )
        self.gui.ui.elapsedTimeLabel.setText( str( datetime.timedelta( seconds = self.taskState.elapsedTime ) ) )
        for ck in self.taskState.computers:
            self.__addNode( self.taskState.computers[ ck ].nodeId, self.taskState.computers[ ck ].subtaskState.subtaskId,  self.taskState.computers[ ck ].subtaskState.subtaskStatus )

    ###########################
    def __updateNodeAdditionalInfo( self, nodeId ):
        comp = self.taskState.computers[ nodeId ]

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

        self.__updateNodeAdditionalInfo( nodeId )

    # SLOTS
    ###########################
    def __nodesTabelRowClicked( self, r, c ):

        nodeId = "{}".format( self.gui.ui.nodesTableWidget.itemAt( r, 0 ).text() )
        self.__updateNodeAdditionalInfo( nodeId )

    ###########################
    def __closeButtonClicked( self ):
        self.gui.window.close()
