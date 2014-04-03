
from PyQt4 import QtCore, QtGui
from ui_nodetasks import Ui_NodeTasksWidget
from progressbar import createWrappedProgressBar

class NodeTasksWidget(QtGui.QWidget):
    
    ########################
    def __init__(self, parent):
        QtGui.QWidget.__init__(self, parent)

        # Set up the user interface from Designer.
        self.ui = Ui_NodeTasksWidget()
        self.ui.setupUi(self)
        self.remoteChunksTable = self.ui.tableRemoteChunks
        self.localTasksTable = self.ui.tableLocalTasks
        self.remoteChunksTableData = []
        self.localTasksTableData = []

        self.chunkIdToRowNumMapping = {}
        self.taskIdToRowNumMapping = {}

        self.currNodeDataState = None

        self.localTasksTable.selectionModel().selectionChanged.connect( self.localTaskRowSelectionChanged )
        self.remoteChunksTable.selectionModel().selectionChanged.connect( self.remoteChunkRowSelectionChanged )

        self.localTasksActiveRow = -1
        self.remoteChunkActiveRow = -1

        self.__resetDetailedTaskView()
        self.__resetDetailedChunkView()

    ########################
    def setNodeUid( self, uid ):
        self.ui.nodeUidLabel.setText( uid )

    ########################
    def updateNodeViewData( self, nodeDataState ):

        self.currNodeDataState = nodeDataState

        # remove old tasks and chunks
        for t in self.taskIdToRowNumMapping:
            if t not in nodeDataState.localTasksStateData:
                rowToRemove = self.taskIdToRowNumMapping[ t ]
                del self.localTasksTableData[ rowToRemove ]
                self.localTasksTable.removeRow( rowToRemove )
                
        self.__remapTaskIdRowMapping()

        for t in self.chunkIdToRowNumMapping:
            if t not in nodeDataState.remoteChunksStateData:
                rowToRemove = self.chunkIdToRowNumMapping[ t ]
                del self.remoteChunksTableData[ rowToRemove ]
                self.remoteChunksTable.removeRow( rowToRemove )
            
        self.__remapChunkIdRowMapping()    

        # register new rows

        for t in nodeDataState.localTasksStateData:
            if t not in self.taskIdToRowNumMapping:
                self.localTasksTableData.append( self.__createRow( t, self.localTasksTable, True ) )
                self.__remapTaskIdRowMapping()

        for t in nodeDataState.remoteChunksStateData:
            if t not in self.chunkIdToRowNumMapping:
                self.remoteChunksTableData.append( self.__createRow( t, self.remoteChunksTable, False ) )
                self.__remapChunkIdRowMapping()


        # update view
        for t in nodeDataState.localTasksStateData:
            self.__updateExistingRowView( self.localTasksTableData[ self.taskIdToRowNumMapping[ t ] ], t, nodeDataState.localTasksStateData[ t ][ "taskProgress" ] )

        for t in nodeDataState.remoteChunksStateData:
            self.__updateExistingRowView( self.remoteChunksTableData[ self.chunkIdToRowNumMapping[ t ] ], t, nodeDataState.remoteChunksStateData[ t ][ "chunkProgress" ] )

        self.__resetDetailedTaskView()
        self.__resetDetailedChunkView()

        
        self.__updateDetailedTaksView( self.localTasksActiveRow )

        self.__updateDetailedChunkView( self.remoteChunkActiveRow )


    ######################## 
    def localTaskRowSelectionChanged( self, item1, item2 ):

        indices = item1.indexes()

        if len( indices ) > 0:
            idx = indices[ 0 ].row()

            self.localTasksActiveRow = idx

            self.__updateDetailedTaksView( idx )
        else:
            self.localTasksActiveRow = -1

        print "Local Task Acctive Row is {}".format( self.localTasksActiveRow )

    ######################## 
    def remoteChunkRowSelectionChanged( self, item1, item2 ):

        indices = item1.indexes()

        if len( indices ) > 0:
            idx = indices[ 0 ].row()

            self.remoteChunkActiveRow = idx

            self.__updateDetailedChunkView( idx )
        else:
            self.remoteChunkActiveRow = -1

        print "Remote Chunk Acctive Row is {}".format( self.remoteChunkActiveRow )


    ########################
    def __remapTaskIdRowMapping( self ):

        self.taskIdToRowNumMapping.clear()

        idx = 0
        for lttData in self.localTasksTableData:
            uid = str( lttData.uid.text() )
            self.taskIdToRowNumMapping[ uid ] = idx
            idx += 1

    ########################
    def __remapChunkIdRowMapping( self ):

        self.chunkIdToRowNumMapping.clear()

        idx = 0
        for rctData in self.remoteChunksTableData:
            uid = str( rctData.uid.text() )
            self.chunkIdToRowNumMapping[ uid ] = idx
            idx += 1


    ########################
    def __createRow( self, uid, table, red = False ):
        nextRow = table.rowCount()
        
        table.insertRow( nextRow )

        item0 = QtGui.QTableWidgetItem()

        item0.setText( uid )

        table.setItem( nextRow, 0, item0 )

        progress = self.__addProgressBar( table, nextRow, 1, red )

        return TableRowDataEntry( item0, progress )

    ########################
    def __addProgressBar( self, table, row, col, red = False ):
        w, p = createWrappedProgressBar( red )
        table.setCellWidget( row, col, w )
        return p

    ########################
    def __updateExistingRowView( self, rowData, taskId, progress ):
        rowData.uid.setText( taskId )
        rowData.progressBar.setProperty("value", int( 100.0 * progress ) )

    def __updateDetailedTaksView( self, idx ):

        if idx >= 0 and idx < len( self.localTasksTableData ):

            uid = str( self.localTasksTableData[ idx ].uid.text() )

            localTaskState = self.currNodeDataState.localTasksStateData[ uid ]

            self.ui.labelDetailedLocalTask.setText( "{}".format( uid ) )
            self.ui.locTaskShortDescrInput.setText( localTaskState[ "ltshd" ] )
            self.ui.allocatedTasksInput.setText( localTaskState[ "allocTasks" ] )
            self.ui.allocatedChunksInput.setText( localTaskState[ "allocChunks" ] )
            self.ui.activeTasksInput.setText( localTaskState[ "activeTasks" ] )
            self.ui.activeChunksInput.setText( localTaskState[ "activeChunks" ] )
            self.ui.chunksLeftInput.setText( localTaskState[ "chunksLeft" ] )
            self.ui.localTaskProgressBar.setProperty( "value", int( 100.0 * localTaskState[ "taskProgress" ] ) )

    def __updateDetailedChunkView( self, idx ):

        if idx >= 0 and idx < len( self.remoteChunksTableData ):

            uid = str( self.remoteChunksTableData[ idx ].uid.text() )

            remoteChunkState = self.currNodeDataState.remoteChunksStateData[ uid ]

            self.ui.labelDetailedRemoteTask.setText( "{}".format( uid ) )
            self.ui.chunkShortDescrInput.setText( remoteChunkState[ "cshd" ] )
            self.ui.cpuPowerInput.setText( remoteChunkState[ "cpuPower" ] )
            self.ui.timeLeftInput.setText( remoteChunkState[ "timeLeft" ] )
            self.ui.activeChunkProgressBar.setProperty( "value", int( 100.0 * remoteChunkState[ "chunkProgress" ] ) )

    ########################
    def __resetDetailedTaskView( self ):
        self.ui.labelDetailedLocalTask.setText( "none" )
        self.ui.locTaskShortDescrInput.setText( "" )
        self.ui.allocatedTasksInput.setText( "" )
        self.ui.allocatedChunksInput.setText( "" )
        self.ui.activeTasksInput.setText( "" )
        self.ui.activeChunksInput.setText( "" )
        self.ui.chunksLeftInput.setText( "" )
        self.ui.localTaskProgressBar.setProperty( "value", 0 )

    ########################
    def __resetDetailedChunkView( self ):
        self.ui.labelDetailedRemoteTask.setText( "none" )
        self.ui.chunkShortDescrInput.setText( "" )
        self.ui.cpuPowerInput.setText( "" )
        self.ui.timeLeftInput.setText( "" )
        self.ui.activeChunkProgressBar.setProperty( "value", 0 )

class TableRowDataEntry:

    ########################
    def __init__( self, uidItem, progressBar ):
        self.uid = uidItem
        self.progressBar = progressBar