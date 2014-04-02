from PyQt4 import QtCore, QtGui
from ui_nodetasks import Ui_NodeTasksWidget

class NodeTasksWidget(QtGui.QWidget):
    
    ########################
    def __init__(self, parent):
        QtGui.QWidget.__init__(self, parent)

        # Set up the user interface from Designer.
        self.ui = Ui_NodeTasksWidget()
        self.ui.setupUi(self)
        self.remoteTaskTable = self.ui.tableRemoteTasks
        self.localTaskTable = self.ui.tableLocalTasks
        self.remoteTasksTableData = {}
        self.localTasksTableData = {}

    ########################
    def setNodeUid( self, uid ):
        self.ui.nodeUidLabel.setText( uid )

    ########################
    def updateNodeViewData( self, nodeDataState ):
        for t in nodeDataState.localTasksStateData:
            if t[ "taskId" ] not in self.localTasksTableData:
                self.__registerRowData( t[ "taskId" ], self.__createRow( t[ "taskId" ], self.localTaskTable ), self.localTasksTableData )

        for t in nodeDataState.remoteChunksStateData:
            if t[ "chunkId" ] not in self.remoteTasksTableData:
                self.__registerRowData( t[ "chunkId" ], self.__createRow( t[ "chunkId" ], self.remoteTaskTable ), self.remoteTasksTableData )


        for t in nodeDataState.localTasksStateData:
            self.__updateExistingRowView( self.localTasksTableData[ t[ "taskId" ] ], t[ "taskId" ], t[ "taskProgress" ] )

        for t in nodeDataState.remoteChunksStateData:
            self.__updateExistingRowView( self.remoteTasksTableData[ t[ "chunkId" ] ], t[ "chunkId" ], t[ "chunkProgress" ] )

        

    ########################
    def __createRow( self, taskUid, table ):
        nextRow = table.rowCount()
        
        table.insertRow( nextRow )

        item0 = QtGui.QTableWidgetItem()

        table.setItem( nextRow, 0, item0 )

        progress = self.__addProgressBar( table, nextRow, 1, True )

        return TableRowDataEntry( item0, progress )

    ########################
    def __addProgressBar( self, table, row, col, red = False ):
        w, p = self.__createWrappedProgressBar( red )
        table.setCellWidget( row, col, w )
        return p

    ########################
    def __createWrappedProgressBar( self, red ):

        widget = QtGui.QWidget()
        widget.setFixedSize( 166, 22 )

        progressBar = QtGui.QProgressBar( widget )
        progressBar.setGeometry(7, 2, 159, 16)
        progressBar.setProperty("value", 0)

        if red:
            progressBar.setStyleSheet(" QProgressBar { border: 2px solid grey; border-radius: 0px; text-align: center; } QProgressBar::chunk {background-color: #dd3a36; width: 1px;}" )
        else:
            progressBar.setStyleSheet(" QProgressBar { border: 2px solid grey; border-radius: 0px; text-align: center; } QProgressBar::chunk {background-color: #3add36; width: 1px;}" )

        return widget, progressBar

    ########################
    def __registerRowData( self, taskUid, rowDataEntry, taskTableData ):
        taskTableData[ taskUid ] = rowDataEntry

    ########################
    def __updateExistingRowView( self, rowData, taskId, progress ):
        rowData.uid.setText( taskId )
        rowData.progressBar.setProperty("value", int( 100.0 * progress ) )

class TableRowDataEntry:

    ########################
    def __init__( self, uidItem, progressBar ):
        self.uid = uidItem
        self.progressBar = progressBar