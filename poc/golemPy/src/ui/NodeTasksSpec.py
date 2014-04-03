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
                del self.taskIdToRowNumMapping[ t ]
                del self.localTasksTableData[ rowToRemove ]
                self.localTasksTable.removeRow( rowToRemove )

        for t in self.chunkIdToRowNumMapping:
            if t not in nodeDataState.remoteChunksStateData:
                rowToRemove = self.chunkIdToRowNumMapping[ t ]
                del self.chunkIdToRowNumMapping[ t ]
                del self.remoteChunksTableData[ rowToRemove ]
                self.remoteChunksTable.removeRow( rowToRemove )

        # register new rows

        for t in nodeDataState.localTasksStateData:
            if t not in self.taskIdToRowNumMapping:
                self.taskIdToRowNumMapping[ t ] = self.localTasksTable.rowCount()
                self.localTasksTableData.append( self.__createRow( t, self.localTasksTable, True ) )

        for t in nodeDataState.remoteChunksStateData:
            if t not in self.chunkIdToRowNumMapping:
                self.chunkIdToRowNumMapping[ t ] = self.remoteChunksTable.rowCount()
                self.remoteChunksTableData.append( self.__createRow( t, self.remoteChunksTable, False ) )


        # update view
        for t in nodeDataState.localTasksStateData:
            self.__updateExistingRowView( self.localTasksTableData[ self.taskIdToRowNumMapping[ t ] ], t, nodeDataState.localTasksStateData[ t ][ "taskProgress" ] )

        for t in nodeDataState.remoteChunksStateData:
            self.__updateExistingRowView( self.remoteChunksTableData[ self.chunkIdToRowNumMapping[ t ] ], t, nodeDataState.remoteChunksStateData[ t ][ "chunkProgress" ] )

        

    ########################
    def __createRow( self, uid, table, red = False ):
        nextRow = table.rowCount()
        
        table.insertRow( nextRow )

        item0 = QtGui.QTableWidgetItem()

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

class TableRowDataEntry:

    ########################
    def __init__( self, uidItem, progressBar ):
        self.uid = uidItem
        self.progressBar = progressBar