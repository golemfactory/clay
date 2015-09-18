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

    def __init__(self, running, uid, timestamp, endpoint, num_peers, num_tasks, last_msg, ltsd, rcsd):
        self.is_running = running
        self.uid = uid
        self.timestamp = timestamp
        self.endpoint = endpoint
        self.num_peers = num_peers
        self.num_tasks = num_tasks
        self.last_msg = last_msg
        self.local_tasks_state_data = ltsd
        self.remote_chunks_state_data = rcsd
        self.addr = ''


# FIXME: add start local task button to manager (should trigger another local task for selected node)
# FIXME: rething deleting nodes which seem to be inactive
class TableRowDataEntry:

    def __init__(self, uid_item, address, remote_chunks_count, local_tasks_count, timestampItem,):
        self.uid = uid_item
        self.endpoint  = address
        self.timestamp = timestampItem
        self.remote_chunks_count = remote_chunks_count
        self.local_tasks_count = local_tasks_count


class ManagerUiCustomizer(QtCore.QObject):

    def __init__(self, widget, manager_logic):
        super(ManagerUiCustomizer, self).__init__()

        self.window = widget.window
        self.ui = widget.ui
        self.table = self.ui.nodeTableWidget
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table_data = {}
        self.node_data_states = []
        self.uid_row_mapping = {}
        self.logic = manager_logic
        self.detailed_view_enabled = False
        self.cur_active_row_idx = None
        self.cur_active_row_uid = None
        self.node_task_widgets = {}

        self.__setup_connections()

    def __setup_connections (self):
        self.table.selectionModel().selectionChanged.connect(self.row_selection_changed)
        self.ui.runAdditionalNodesPushButton.clicked.connect(self.add_nodes_clicked)
        self.ui.runAdditionalLocalNodesPushButton.clicked.connect(self.add_local_nodes_clicked)
        self.ui.stopNodePushButton.clicked.connect(self.stop_node_clicked)
        self.ui.enqueueTaskButton.clicked.connect(self.enqueue_task_clicked)
        self.ui.terminateAllNodesPushButton.clicked.connect(self.terminate_all_nodes_clicked)
        self.ui.terminateAllLocalNodesButton.clicked.connect(self.terminate_all_local_nodes_clicked)
        self.table.cell_double_clicked.connect(self.cell_double_clicked)

    def add_nodes_clicked(self):
        num_nodes = self.ui.additionalNodesSpinBox.value()
        self.logic.run_additional_nodes(num_nodes)

    def add_local_nodes_clicked(self):
        if self.cur_active_row_idx is not None and self.cur_active_row_uid is not None:
            num_nodes = self.ui.additionalLocalNodesSpinBox.value()
            self.logic.runAdditionalLocalNodes(self.cur_active_row_uid, num_nodes)

    def stop_node_clicked(self):
        if self.cur_active_row_idx is not None and self.cur_active_row_uid is not None:
            self.logic.terminate_node(self.cur_active_row_uid)

    def terminate_all_nodes_clicked(self):
        self.logic.terminate_all_nodes()

    def terminate_all_local_nodes_clicked(self):
        if self.cur_active_row_idx is not None and self.cur_active_row_uid is not None:
            self.logic.terminate_all_local_nodes(self.cur_active_row_uid)

    def enqueue_task_clicked(self):
        if self.cur_active_row_idx is not None and self.cur_active_row_uid is not None:
            uid = self.cur_active_row_uid
            file_path = QFileDialog.getOpenFileName(self.window, "Choose task file", "", "Golem Task (*.gt)")
            if os.path.exists(file_path):
                self.logic.load_task(uid, file_path)
#        dialog = TaskSpecDialog(self.table)
#        if dialog.exec_():
#            w = dialog.getWidth()
#            h = dialog.getHeight()
#            n = dialog.getNumSamplesPerPixel()
#            p = dialog.getFileName()

 #           self.logic.enqueue_new_task(self.cur_active_row_uid, w, h, n, p)

    def row_selection_changed(self, item1, item2):
        if not self.detailed_view_enabled:
            self.detailed_view_enabled = True
            self.enable_detailed_view(True)

        indices = item1.indexes()

        if len(indices) > 0 and len(self.node_data_states) > 0:
            idx = indices[ 0 ].row()
            
            if idx >= len(self.node_data_states):
                idx = len(self.node_data_states) - 1

            uid = self.node_data_states[ idx ].uid
            self.cur_active_row_idx = idx
            self.cur_active_row_uid = uid

            #self.__update_detailed_node_view(idx, self.node_data_states[ idx ])
        else:
            self.detailed_view_enabled = False
            self.__reset_detailed_view()
            self.enable_detailed_view(False)

    def cell_double_clicked(self, row, column):

        w = NodeTasksWidget(None)
        w.setNodeUid("Node UID: {}".format(self.cur_active_row_uid))
        self.node_task_widgets[ self.cur_active_row_uid ] = w
        w.show()

    def __create_row(self, node_uid, node_time):
        next_row = self.table.rowCount()
        
        self.table.insertRow(next_row)

        item0 = QtGui.QTableWidgetItem()
        item1 = QtGui.QTableWidgetItem()

        self.table.setItem(next_row, 0, item0)
        self.table.setItem(next_row, 1, item1)

        item2 = QtGui.QTableWidgetItem()
        item3 = QtGui.QTableWidgetItem()

        self.table.setItem(next_row, 2, item2)
        self.table.setItem(next_row, 3, item3)

        item4 = QtGui.QTableWidgetItem()

        self.table.setItem(next_row, 4, item4)

        assert node_uid not in self.table_data

        return TableRowDataEntry(item0, item1, item2, item3, item4)

    def __update_exisiting_row_view(self, row_data, node_uid, node_timestamp, remote_chunks_count, local_tasks_count, endpoint):
        row_data.uid.setText(node_uid)
        row_data.endpoint.setText(endpoint)
        row_data.timestamp.setText(node_timestamp)
        row_data.remote_chunks_count.setText(str(remote_chunks_count))
        row_data.local_tasks_count.setText(str(local_tasks_count))

    def __update_detailed_node_view(self, idx, node_data_state):
        if self.detailed_view_enabled and self.cur_active_row_idx == idx:

            self.ui.endpointInput.setText(node_data_state.endpoint)
            self.ui.noPeersInput.setText(node_data_state.num_peers)
            self.ui.noTasksInput.setText(node_data_state.num_tasks)
            self.ui.lastMsgInput.setText(node_data_state.last_msg)

    def __reset_detailed_view(self):
        self.ui.endpointInput.setText("")
        self.ui.noPeersInput.setText("")
        self.ui.noTasksInput.setText("")
        self.ui.lastMsgInput.setText("")

    def __register_row_data(self, node_uid, row_data_entry, node_data_state):
        self.table_data[ node_uid ] = row_data_entry
        self.uid_row_mapping[ node_uid ] = len(self.node_data_states)
        self.node_data_states.append(node_data_state)

    def __remove_row_and_detailed_data(self, idx, uid):
        logger.debug("Removing {} idx from {} total at {} uid".format(idx, len(self.table_data), uid))
        self.node_data_states.pop(idx)
        del self.table_data[ uid ]
        self.table.removeRow(idx)

        self.uid_row_mapping = {}
        for i, nds in enumerate(self.node_data_states):
            self.uid_row_mapping[ nds.uid ] = i

        cur_row = self.table.currentRow()

        if cur_row is not None and cur_row >= 0:
            self.cur_active_row_idx = cur_row
            self.cur_active_row_uid = self.node_data_states[ cur_row ].uid

    def is_registered(self, node_uid):
        return node_uid in self.table_data

    def enable_detailed_view(self, enable_flag):
        if not enable_flag:
            self.__reset_detailed_view()

        self.ui.frameDetailedNode.setEnabled(enable_flag)

    def update_node_presentation_state(self, node_data_state):
        #prerequisites
        if not self.is_registered(node_data_state.uid):
            self.__register_row_data(node_data_state.uid, self.__create_row(node_data_state.uid, node_data_state.timestamp), node_data_state)

        #update model
        idx = self.uid_row_mapping[ node_data_state.uid ]
        self.node_data_states[ idx ] = node_data_state

        #update view
        if node_data_state.is_running:
            self.__update_exisiting_row_view(self.table_data[ node_data_state.uid ],
                                          node_data_state.uid,
                                          node_data_state.timestamp,
                                          len(node_data_state.remote_chunks_state_data),
                                          len(node_data_state.local_tasks_state_data),
                                          node_data_state.endpoint)
            self.__update_detailed_node_view(idx, node_data_state)
        else:
            self.__remove_row_and_detailed_data(idx, node_data_state.uid)

        if node_data_state.uid in self.node_task_widgets:
            self.node_task_widgets[ node_data_state.uid ].update_node_view_data(node_data_state)
