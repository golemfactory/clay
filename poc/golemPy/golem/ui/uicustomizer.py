from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QFileDialog
from NodeTasksSpec import NodeTasksWidget
import logging
import os

logger = logging.getLogger(__name__)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class NodeDataState:

    ########################
    def __init__(self, running, uid, timestamp, endpoint, numPeers, num_tasks, lastMsg, ltsd, rcsd):
        self.is_running = running
        self.uid = uid
        self.timestamp = timestamp
        self.endpoint = endpoint
        self.numPeers = numPeers
        self.num_tasks = num_tasks
        self.lastMsg = lastMsg
        self.localTasksStateData = ltsd
        self.remoteChunksStateData = rcsd
        self.addr = ''

#FIXME: add start local task button to manager (should trigger another local task for selected node)
#FIXME: rething deleting nodes which seem to be inactive
class TableRowDataEntry:

    ########################
    def __init__(self, uidItem, address, remoteChunksCount, localTasksCount, timestampItem,):
        self.uid = uidItem
        self.endpoint  = address
        self.timestamp = timestampItem
        self.remoteChunksCount = remoteChunksCount
        self.localTasksCount = localTasksCount

class ManagerUiCustomizer(QtCore.QObject):

    ########################
    def __init__(self, widget, manager_logic):
        super(ManagerUiCustomizer, self).__init__()

        self.window = widget.window
        self.ui = widget.ui
        self.table = self.ui.nodeTableWidget
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.tableData = {}
        self.node_data_states = []
        self.uid_row_mapping = {}
        self.logic = manager_logic
        self.detailedViewEnabled = False
        self.curActiveRowIdx = None
        self.curActiveRowUid = None
        self.nodeTaskWidgets = {}

        self.__setup_connections()

    def __setup_connections (self):
        self.table.selectionModel().selectionChanged.connect(self.row_selection_changed)
        self.ui.runAdditionalNodesPushButton.clicked.connect(self.add_nodes_clicked)
        self.ui.runAdditionalLocalNodesPushButton.clicked.connect(self.add_local_nodes_clicked)
        self.ui.stopNodePushButton.clicked.connect(self.stop_node_clicked)
        self.ui.enqueueTaskButton.clicked.connect(self.enqueue_task_clicked)
        self.ui.terminateAllNodesPushButton.clicked.connect(self.terminate_all_nodes_clicked)
        self.ui.terminateAllLocalNodesButton.clicked.connect(self.terminate_all_local_nodes_clicked)
        self.table.cellDoubleClicked.connect(self.cellDoubleClicked)

    ########################
    def add_nodes_clicked(self):
        num_nodes = self.ui.additionalNodesSpinBox.value()
        self.logic.run_additional_nodes(num_nodes)

    ########################
    def add_local_nodes_clicked(self):
        if self.curActiveRowIdx is not None and self.curActiveRowUid is not None:
            num_nodes = self.ui.additionalLocalNodesSpinBox.value()
            self.logic.runAdditionalLocalNodes(self.curActiveRowUid, num_nodes)

    ########################
    def stop_node_clicked(self):
        if self.curActiveRowIdx is not None and self.curActiveRowUid is not None:
            self.logic.terminate_node(self.curActiveRowUid)

    ########################
    def terminate_all_nodes_clicked(self):
        self.logic.terminate_all_nodes()

    ########################
    def terminate_all_local_nodes_clicked(self):
        if self.curActiveRowIdx is not None and self.curActiveRowUid is not None:
            self.logic.terminate_all_local_nodes(self.curActiveRowUid)

    ########################
    def enqueue_task_clicked(self):
        if self.curActiveRowIdx is not None and self.curActiveRowUid is not None:
            uid = self.curActiveRowUid
            file_path = QFileDialog.getOpenFileName(self.window, "Choose task file", "", "Golem Task (*.gt)")
            if os.path.exists(file_path):
                self.logic.load_task(uid, file_path)
#        dialog = TaskSpecDialog(self.table)
#        if dialog.exec_():
#            w = dialog.getWidth()
#            h = dialog.getHeight()
#            n = dialog.getNumSamplesPerPixel()
#            p = dialog.getFileName()

 #           self.logic.enqueue_new_task(self.curActiveRowUid, w, h, n, p)

    ########################
    def row_selection_changed(self, item1, item2):
        if not self.detailedViewEnabled:
            self.detailedViewEnabled = True
            self.enableDetailedView(True)

        indices = item1.indexes()

        if len(indices) > 0 and len(self.node_data_states) > 0:
            idx = indices[ 0 ].row()
            
            if idx >= len(self.node_data_states):
                idx = len(self.node_data_states) - 1

            uid = self.node_data_states[ idx ].uid
            self.curActiveRowIdx = idx
            self.curActiveRowUid = uid

            #self.__updateDetailedNodeView(idx, self.node_data_states[ idx ])
        else:
            self.detailedViewEnabled = False
            self.__resetDetailedView()
            self.enableDetailedView(False)

    def cellDoubleClicked(self, row, column):

        w = NodeTasksWidget(None)
        w.setNodeUid("Node UID: {}".format(self.curActiveRowUid))
        self.nodeTaskWidgets[ self.curActiveRowUid ] = w
        w.show()

    ########################
    def __createRow(self, nodeUid, nodeTime):
        nextRow = self.table.rowCount()
        
        self.table.insertRow(nextRow)

        item0 = QtGui.QTableWidgetItem()
        item1 = QtGui.QTableWidgetItem()

        self.table.setItem(nextRow, 0, item0)
        self.table.setItem(nextRow, 1, item1)

        item2 = QtGui.QTableWidgetItem()
        item3 = QtGui.QTableWidgetItem()

        self.table.setItem(nextRow, 2, item2)
        self.table.setItem(nextRow, 3, item3)

        item4 = QtGui.QTableWidgetItem()

        self.table.setItem(nextRow, 4, item4)

        assert nodeUid not in self.tableData

        return TableRowDataEntry(item0, item1, item2, item3, item4)

    ########################
    def __updateExistingRowView(self, rowData, nodeUid, nodeTimestamp, remoteChunksCount, localTasksCount, endpoint):
        rowData.uid.setText(nodeUid)
        rowData.endpoint.setText(endpoint)
        rowData.timestamp.setText(nodeTimestamp)
        rowData.remoteChunksCount.setText(str(remoteChunksCount))
        rowData.localTasksCount.setText(str(localTasksCount))


    ########################
    def __updateDetailedNodeView(self, idx, node_data_state):
        if self.detailedViewEnabled and self.curActiveRowIdx == idx:

            self.ui.endpointInput.setText(node_data_state.endpoint)
            self.ui.noPeersInput.setText(node_data_state.numPeers)
            self.ui.noTasksInput.setText(node_data_state.num_tasks)
            self.ui.lastMsgInput.setText(node_data_state.lastMsg)

    ########################
    def __resetDetailedView(self):
        self.ui.endpointInput.setText("")
        self.ui.noPeersInput.setText("")
        self.ui.noTasksInput.setText("")
        self.ui.lastMsgInput.setText("")

    ########################
    def __registerRowData(self, nodeUid, rowDataEntry, node_data_state):
        self.tableData[ nodeUid ] = rowDataEntry
        self.uid_row_mapping[ nodeUid ] = len(self.node_data_states)
        self.node_data_states.append(node_data_state)

    ########################
    def __removeRowAndDetailedData(self, idx, uid):
        logger.debug("Removing {} idx from {} total at {} uid".format(idx, len(self.tableData), uid))
        self.node_data_states.pop(idx)
        del self.tableData[ uid ]
        self.table.removeRow(idx)

        self.uid_row_mapping = {}
        for i, nds in enumerate(self.node_data_states):
            self.uid_row_mapping[ nds.uid ] = i

        curRow = self.table.currentRow()

        if curRow is not None and curRow >= 0:
            self.curActiveRowIdx = curRow
            self.curActiveRowUid = self.node_data_states[ curRow ].uid

    ########################
    def isRegistered(self, nodeUid):
        return nodeUid in self.tableData

    ########################
    def enableDetailedView(self, enableFlag):
        if not enableFlag:
            self.__resetDetailedView()

        self.ui.frameDetailedNode.setEnabled(enableFlag)

    ########################
    def UpdateNodePresentationState(self, node_data_state):
        #prerequisites
        if not self.isRegistered(node_data_state.uid):
            self.__registerRowData(node_data_state.uid, self.__createRow(node_data_state.uid, node_data_state.timestamp), node_data_state)

        #update model
        idx = self.uid_row_mapping[ node_data_state.uid ]
        self.node_data_states[ idx ] = node_data_state

        #update view
        if node_data_state.is_running:
            self.__updateExistingRowView(self.tableData[ node_data_state.uid ],
                                          node_data_state.uid,
                                          node_data_state.timestamp,
                                          len(node_data_state.remoteChunksStateData),
                                          len(node_data_state.localTasksStateData),
                                          node_data_state.endpoint)
            self.__updateDetailedNodeView(idx, node_data_state)
        else:
            self.__removeRowAndDetailedData(idx, node_data_state.uid)

        if node_data_state.uid in self.nodeTaskWidgets:
            self.nodeTaskWidgets[ node_data_state.uid ].updateNodeViewData(node_data_state)
