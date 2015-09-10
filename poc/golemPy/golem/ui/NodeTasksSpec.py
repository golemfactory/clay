
from PyQt4 import QtCore, QtGui
from gen.ui_nodetasks import Ui_NodeTasksWidget
from progressbar import create_wrapped_progress_bar
import logging

logger = logging.getLogger(__name__)

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

        self.chunk_idToRowNumMapping = {}
        self.task_idToRowNumMapping = {}

        self.currNodeDataState = None

        self.localTasksTable.selectionModel().selectionChanged.connect(self.localTaskRowSelectionChanged)
        self.remoteChunksTable.selectionModel().selectionChanged.connect(self.remoteChunkRowSelectionChanged)

        self.localTasksActiveRow = -1
        self.remoteChunkActiveRow = -1

        self.__resetDetailedTaskView()
        self.__resetDetailedChunkView()

    ########################
    def setNodeUid(self, uid):
        self.ui.nodeUidLabel.setText(uid)

    ########################
    def updateNodeViewData(self, node_data_state):

        self.currNodeDataState = node_data_state

        # remove old tasks and chunks
        for t in self.task_idToRowNumMapping:
            if t not in node_data_state.localTasksStateData:
                rowToRemove = self.task_idToRowNumMapping[ t ]
                del self.localTasksTableData[ rowToRemove ]
                self.localTasksTable.removeRow(rowToRemove)
                
        self.__remapTaskIdRowMapping()

        for t in self.chunk_idToRowNumMapping:
            if t not in node_data_state.remoteChunksStateData:
                rowToRemove = self.chunk_idToRowNumMapping[ t ]
                del self.remoteChunksTableData[ rowToRemove ]
                self.remoteChunksTable.removeRow(rowToRemove)
            
        self.__remapChunkIdRowMapping()    

        # register new rows

        for t in node_data_state.localTasksStateData:
            if t not in self.task_idToRowNumMapping:
                self.localTasksTableData.append(self.__createRow(t, self.localTasksTable, True))
                self.__remapTaskIdRowMapping()

        for t in node_data_state.remoteChunksStateData:
            if t not in self.chunk_idToRowNumMapping:
                self.remoteChunksTableData.append(self.__createRow(t, self.remoteChunksTable, False))
                self.__remapChunkIdRowMapping()


        # update view
        for t in node_data_state.localTasksStateData:
            self.__updateExistingRowView(self.localTasksTableData[ self.task_idToRowNumMapping[ t ] ], t, node_data_state.localTasksStateData[ t ][ "taskProgress" ])

        for t in node_data_state.remoteChunksStateData:
            self.__updateExistingRowView(self.remoteChunksTableData[ self.chunk_idToRowNumMapping[ t ] ], t, node_data_state.remoteChunksStateData[ t ][ "chunkProgress" ])

        self.__resetDetailedTaskView()
        self.__resetDetailedChunkView()

        
        self.__updateDetailedTaksView(self.localTasksActiveRow)

        self.__update_detailed_chunk_view(self.remoteChunkActiveRow)


    ######################## 
    def localTaskRowSelectionChanged(self, item1, item2):

        indices = item1.indexes()

        if len(indices) > 0:
            idx = indices[ 0 ].row()

            self.localTasksActiveRow = idx

            self.__updateDetailedTaksView(idx)
        else:
            self.localTasksActiveRow = -1

        logger.debug("Local Task Acctive Row is {}".format(self.localTasksActiveRow))

    ######################## 
    def remoteChunkRowSelectionChanged(self, item1, item2):

        indices = item1.indexes()

        if len(indices) > 0:
            idx = indices[ 0 ].row()

            self.remoteChunkActiveRow = idx

            self.__update_detailed_chunk_view(idx)
        else:
            self.remoteChunkActiveRow = -1

        logger.debug("Remote Chunk Acctive Row is {}".format(self.remoteChunkActiveRow))


    ########################
    def __remapTaskIdRowMapping(self):

        self.task_idToRowNumMapping.clear()

        idx = 0
        for lttData in self.localTasksTableData:
            uid = str(lttData.uid.text())
            self.task_idToRowNumMapping[ uid ] = idx
            idx += 1

    ########################
    def __remapChunkIdRowMapping(self):

        self.chunk_idToRowNumMapping.clear()

        idx = 0
        for rctData in self.remoteChunksTableData:
            uid = str(rctData.uid.text())
            self.chunk_idToRowNumMapping[ uid ] = idx
            idx += 1


    ########################
    def __createRow(self, uid, table, red = False):
        nextRow = table.rowCount()
        
        table.insertRow(nextRow)

        item0 = QtGui.QTableWidgetItem()

        item0.setText(uid)

        table.setItem(nextRow, 0, item0)

        progress = self.__addProgressBar(table, nextRow, 1, red)

        return TableRowDataEntry(item0, progress)

    ########################
    def __addProgressBar(self, table, row, col, red = False):
        w, p = create_wrapped_progress_bar(red)
        table.setCellWidget(row, col, w)
        return p

    ########################
    def __updateExistingRowView(self, rowData, task_id, progress):
        rowData.uid.setText(task_id)
        rowData.progress_bar.setProperty("value", int(100.0 * progress))

    def __updateDetailedTaksView(self, idx):

        if 0 <= idx < len(self.localTasksTableData):

            uid = str(self.localTasksTableData[ idx ].uid.text())

            local_task_state = self.currNodeDataState.localTasksStateData[ uid ]

            self.ui.labelDetailedLocalTask.setText("{}".format(uid))
            self.ui.locTaskShortDescrInput.setText(local_task_state[ "ltshd" ])
            self.ui.allocatedTasksInput.setText(local_task_state[ "allocTasks" ])
            self.ui.allocatedChunksInput.setText(local_task_state[ "alloc_chunks" ])
            self.ui.activeTasksInput.setText(local_task_state[ "active_tasks" ])
            self.ui.activeChunksInput.setText(local_task_state[ "active_chunks" ])
            self.ui.chunksLeftInput.setText(local_task_state[ "chunks_left" ])
            self.ui.localTaskProgressBar.setProperty("value", int(100.0 * local_task_state[ "taskProgress" ]))

    def __update_detailed_chunk_view(self, idx):

        if 0 <= idx < len(self.remoteChunksTableData):

            uid = str(self.remoteChunksTableData[ idx ].uid.text())

            remoteChunkState = self.currNodeDataState.remoteChunksStateData[ uid ]

            self.ui.labelDetailedRemoteTask.setText("{}".format(uid))
            self.ui.chunkShortDescrInput.setText(remoteChunkState[ "cshd" ])
            self.ui.cpuPowerInput.setText(remoteChunkState[ "cpu_power" ])
            self.ui.timeLeftInput.setText(remoteChunkState[ "timeLeft" ])
            self.ui.activeChunkProgressBar.setProperty("value", int(100.0 * remoteChunkState[ "chunkProgress" ]))

    ########################
    def __resetDetailedTaskView(self):
        self.ui.labelDetailedLocalTask.setText("none")
        self.ui.locTaskShortDescrInput.setText("")
        self.ui.allocatedTasksInput.setText("")
        self.ui.allocatedChunksInput.setText("")
        self.ui.activeTasksInput.setText("")
        self.ui.activeChunksInput.setText("")
        self.ui.chunksLeftInput.setText("")
        self.ui.localTaskProgressBar.setProperty("value", 0)

    ########################
    def __resetDetailedChunkView(self):
        self.ui.labelDetailedRemoteTask.setText("none")
        self.ui.chunkShortDescrInput.setText("")
        self.ui.cpuPowerInput.setText("")
        self.ui.timeLeftInput.setText("")
        self.ui.activeChunkProgressBar.setProperty("value", 0)

class TableRowDataEntry:

    ########################
    def __init__(self, uid_item,
                 ):
        self.uid = uid_item
        self.progress_bar = progress_bar