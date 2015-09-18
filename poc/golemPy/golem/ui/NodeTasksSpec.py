
from PyQt4 import QtCore, QtGui
from gen.ui_nodetasks import Ui_NodeTasksWidget
from progressbar import create_wrapped_progress_bar
import logging

logger = logging.getLogger(__name__)


class NodeTasksWidget(QtGui.QWidget):

    def __init__(self, parent):
        QtGui.QWidget.__init__(self, parent)

        # Set up the user interface from Designer.
        self.ui = Ui_NodeTasksWidget()
        self.ui.setupUi(self)
        self.remote_chunks_table = self.ui.tableRemoteChunks
        self.local_tasks_table = self.ui.tableLocalTasks
        self.remote_chunks_table_data = []
        self.local_tasks_table_data = []

        self.chunk_id_to_row_num_mapping = {}
        self.task_id_to_row_num_mapping = {}

        self.curr_node_data_state = None

        self.local_tasks_table.selectionModel().selectionChanged.connect(self.local_task_row_selection_changed)
        self.remote_chunks_table.selectionModel().selectionChanged.connect(self.remote_chunk_row_selection_changed)

        self.local_tasks_active_row = -1
        self.remote_chunk_active_row = -1

        self.__reset_detailed_task_view()
        self.__reset_detailed_chunk_view()

    def set_node_uid(self, uid):
        self.ui.nodeUidLabel.setText(uid)

    def update_node_view_data(self, node_data_state):

        self.curr_node_data_state = node_data_state

        # remove old tasks and chunks
        for t in self.task_id_to_row_num_mapping:
            if t not in node_data_state.local_tasks_state_data:
                row_to_remove = self.task_id_to_row_num_mapping[ t ]
                del self.local_tasks_table_data[ row_to_remove ]
                self.local_tasks_table.removeRow(row_to_remove)
                
        self.__remap_task_id_row_mapping()

        for t in self.chunk_id_to_row_num_mapping:
            if t not in node_data_state.remote_chunks_state_data:
                row_to_remove = self.chunk_id_to_row_num_mapping[ t ]
                del self.remote_chunks_table_data[ row_to_remove ]
                self.remote_chunks_table.removeRow(row_to_remove)
            
        self.__remap_chunk_id_row_mapping()

        # register new rows

        for t in node_data_state.local_tasks_state_data:
            if t not in self.task_id_to_row_num_mapping:
                self.local_tasks_table_data.append(self.__create_row(t, self.local_tasks_table, True))
                self.__remap_task_id_row_mapping()

        for t in node_data_state.remote_chunks_state_data:
            if t not in self.chunk_id_to_row_num_mapping:
                self.remote_chunks_table_data.append(self.__create_row(t, self.remote_chunks_table, False))
                self.__remap_chunk_id_row_mapping()


        # update view
        for t in node_data_state.local_tasks_state_data:
            self.__update_exisiting_row_view(self.local_tasks_table_data[ self.task_id_to_row_num_mapping[ t ] ], t, node_data_state.local_tasks_state_data[ t ][ "taskProgress" ])

        for t in node_data_state.remote_chunks_state_data:
            self.__update_exisiting_row_view(self.remote_chunks_table_data[ self.chunk_id_to_row_num_mapping[ t ] ], t, node_data_state.remote_chunks_state_data[ t ][ "chunkProgress" ])

        self.__reset_detailed_task_view()
        self.__reset_detailed_chunk_view()

        self.__update_detailed_task_view(self.local_tasks_active_row)

        self.__update_detailed_chunk_view(self.remote_chunk_active_row)


    def local_task_row_selection_changed(self, item1, item2):

        indices = item1.indexes()

        if len(indices) > 0:
            idx = indices[ 0 ].row()

            self.local_tasks_active_row = idx

            self.__update_detailed_task_view(idx)
        else:
            self.local_tasks_active_row = -1

        logger.debug("Local Task Acctive Row is {}".format(self.local_tasks_active_row))

    def remote_chunk_row_selection_changed(self, item1, item2):

        indices = item1.indexes()

        if len(indices) > 0:
            idx = indices[ 0 ].row()

            self.remote_chunk_active_row = idx

            self.__update_detailed_chunk_view(idx)
        else:
            self.remote_chunk_active_row = -1

        logger.debug("Remote Chunk Acctive Row is {}".format(self.remote_chunk_active_row))

    def __remap_task_id_row_mapping(self):

        self.task_id_to_row_num_mapping.clear()

        idx = 0
        for lttData in self.local_tasks_table_data:
            uid = str(lttData.uid.text())
            self.task_id_to_row_num_mapping[ uid ] = idx
            idx += 1

    def __remap_chunk_id_row_mapping(self):

        self.chunk_id_to_row_num_mapping.clear()

        idx = 0
        for rctData in self.remote_chunks_table_data:
            uid = str(rctData.uid.text())
            self.chunk_id_to_row_num_mapping[ uid ] = idx
            idx += 1

    def __create_row(self, uid, table, red = False):
        next_row = table.rowCount()
        
        table.insertRow(next_row)

        item0 = QtGui.QTableWidgetItem()

        item0.setText(uid)

        table.setItem(next_row, 0, item0)

        progress = self.__add_progress_bar(table, next_row, 1, red)

        return TableRowDataEntry(item0, progress)

    def __add_progress_bar(self, table, row, col, red = False):
        w, p = create_wrapped_progress_bar(red)
        table.setCellWidget(row, col, w)
        return p

    def __update_exisiting_row_view(self, row_data, task_id, progress):
        row_data.uid.setText(task_id)
        row_data.progress_bar.setProperty("value", int(100.0 * progress))

    def __update_detailed_task_view(self, idx):

        if 0 <= idx < len(self.local_tasks_table_data):

            uid = str(self.local_tasks_table_data[ idx ].uid.text())

            local_task_state = self.curr_node_data_state.local_tasks_state_data[ uid ]

            self.ui.labelDetailedLocalTask.setText("{}".format(uid))
            self.ui.locTaskShortDescrInput.setText(local_task_state[ "ltshd" ])
            self.ui.allocatedTasksInput.setText(local_task_state[ "allocTasks" ])
            self.ui.allocatedChunksInput.setText(local_task_state[ "alloc_chunks" ])
            self.ui.activeTasksInput.setText(local_task_state[ "active_tasks" ])
            self.ui.activeChunksInput.setText(local_task_state[ "active_chunks" ])
            self.ui.chunksLeftInput.setText(local_task_state[ "chunks_left" ])
            self.ui.localTaskProgressBar.setProperty("value", int(100.0 * local_task_state[ "taskProgress" ]))

    def __update_detailed_chunk_view(self, idx):

        if 0 <= idx < len(self.remote_chunks_table_data):

            uid = str(self.remote_chunks_table_data[ idx ].uid.text())

            remote_chunk_state = self.curr_node_data_state.remote_chunks_state_data[ uid ]

            self.ui.labelDetailedRemoteTask.setText("{}".format(uid))
            self.ui.chunkShortDescrInput.setText(remote_chunk_state[ "cshd" ])
            self.ui.cpuPowerInput.setText(remote_chunk_state[ "cpu_power" ])
            self.ui.timeLeftInput.setText(remote_chunk_state[ "timeLeft" ])
            self.ui.activeChunkProgressBar.setProperty("value", int(100.0 * remote_chunk_state[ "chunkProgress" ]))

    def __reset_detailed_task_view(self):
        self.ui.labelDetailedLocalTask.setText("none")
        self.ui.locTaskShortDescrInput.setText("")
        self.ui.allocatedTasksInput.setText("")
        self.ui.allocatedChunksInput.setText("")
        self.ui.activeTasksInput.setText("")
        self.ui.activeChunksInput.setText("")
        self.ui.chunksLeftInput.setText("")
        self.ui.localTaskProgressBar.setProperty("value", 0)

    def __reset_detailed_chunk_view(self):
        self.ui.labelDetailedRemoteTask.setText("none")
        self.ui.chunkShortDescrInput.setText("")
        self.ui.cpuPowerInput.setText("")
        self.ui.timeLeftInput.setText("")
        self.ui.activeChunkProgressBar.setProperty("value", 0)


class TableRowDataEntry:

    def __init__(self, uid_item, progress_bar):
        self.uid = uid_item
        self.progress_bar = progress_bar