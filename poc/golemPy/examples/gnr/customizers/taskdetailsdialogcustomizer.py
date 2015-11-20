import datetime

from PyQt4 import QtCore
from PyQt4.QtGui import QMenu

from golem.task.taskstate import TaskState, ComputerState
from examples.gnr.renderingtaskstate import RenderingTaskState
from subtaskcontextmenucustomizer import SubtaskContextMenuCustomizer

from examples.gnr.ui.subtasktableentry import SubtaskTableElem


class TaskDetailsDialogCustomizer:
    def __init__(self, gui, logic, gnr_task_state):
        #    assert isinstance(gnr_task_state, RenderingTaskState)
        self.gui = gui
        self.logic = logic
        self.gnr_task_state = gnr_task_state

        self.subtask_table_elements = {}

        self.__setup_connections()

        self.update_view(self.gnr_task_state.task_state)

    def update_view(self, task_state):
        self.gnr_task_state.task_state = task_state
        self.__update_data()

    def __update_data(self):
        self.gui.ui.totalTaskProgressBar.setProperty("value", int(self.gnr_task_state.task_state.progress * 100))
        self.gui.ui.estimatedRemainingTimeLabel.setText(
            str(datetime.timedelta(seconds=self.gnr_task_state.task_state.remaining_time)))
        self.gui.ui.elapsedTimeLabel.setText(
            str(datetime.timedelta(seconds=self.gnr_task_state.task_state.elapsed_time)))

        for k in self.gnr_task_state.task_state.subtask_states:
            if k not in self.subtask_table_elements:
                ss = self.gnr_task_state.task_state.subtask_states[k]
                self.__add_node(ss.computer.node_id, ss.subtask_id, ss.subtask_status)

        for k, elem in self.subtask_table_elements.items():
            if elem.subtask_id in self.gnr_task_state.task_state.subtask_states:
                ss = self.gnr_task_state.task_state.subtask_states[elem.subtask_id]
                elem.update(ss.subtask_progress, ss.subtask_status, ss.subtask_rem_time)
            else:
                del self.subtask_table_elements[k]

    def __setup_connections(self):
        QtCore.QObject.connect(self.gui.ui.nodesTableWidget, QtCore.SIGNAL("cellClicked(int, int)"),
                               self.__nodes_table_row_clicked)
        QtCore.QObject.connect(self.gui.ui.nodesTableWidget, QtCore.SIGNAL("itemSelectionChanged()"),
                               self.__nodes_table_row_selected)
        self.gui.ui.nodesTableWidget.customContextMenuRequested.connect(self.__context_menu_requested)
        self.gui.ui.closeButton.clicked.connect(self.__close_button_clicked)

    # ###########################
    # def __initializeData(self):
    #     self.gui.ui.totalTaskProgressBar.setProperty("value", int(self.gnr_task_state.task_state.progress * 100))
    #     self.gui.ui.estimatedRemainingTimeLabel.setText(str(datetime.timedelta(seconds = self.gnr_task_state.task_state.remaining_time)))
    #     self.gui.ui.elapsedTimeLabel.setText(str(datetime.timedelta(seconds = self.gnr_task_state.task_state.elapsed_time)))
    #     for k in self.gnr_task_state.task_state.subtask_states:
    #         if k not in self.subtask_table_elements:
    #             ss = self.gnr_task_state.task_state.subtask_states[ k ]
    #             self.__add_node(ss.computer.node_id, ss.subtask_id, ss.subtask_status)

    def __update_node_additional_info(self, node_id, subtask_id):
        if subtask_id in self.gnr_task_state.task_state.subtask_states:
            ss = self.gnr_task_state.task_state.subtask_states[subtask_id]
            comp = ss.computer

            assert isinstance(comp, ComputerState)

            self.gui.ui.nodeIdLabel.setText(node_id)
            self.gui.ui.nodeIpAddressLabel.setText(comp.ip_address)
            self.gui.ui.performanceLabel.setText("{} rays per sec".format(comp.performance))
            self.gui.ui.subtaskDefinitionTextEdit.setPlainText(ss.subtask_definition)

    def __add_node(self, node_id, subtask_id, status):
        current_row_count = self.gui.ui.nodesTableWidget.rowCount()
        self.gui.ui.nodesTableWidget.insertRow(current_row_count)

        subtask_table_elem = SubtaskTableElem(node_id, subtask_id, status)

        for col in range(0, 4): self.gui.ui.nodesTableWidget.setItem(current_row_count, col,
                                                                     subtask_table_elem.get_column_item(col))

        self.gui.ui.nodesTableWidget.setCellWidget(current_row_count, 4,
                                                   subtask_table_elem.progressBarInBoxLayoutWidget)

        self.subtask_table_elements[subtask_id] = subtask_table_elem

        subtask_table_elem.update(0.0, "", 0.0)

        self.__update_node_additional_info(node_id, subtask_id)

    # SLOTS
    ###########################
    def __nodes_table_row_clicked(self, r, c):

        node_id = "{}".format(self.gui.ui.nodesTableWidget.item(r, 0).text())
        subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(r, 1).text())
        self.__update_node_additional_info(node_id, subtask_id)

    def __nodes_table_row_selected(self):
        if self.gui.ui.nodesTableWidget.selectedItems():
            row = self.gui.ui.nodesTableWidget.selectedItems()[0].row()
            node_id = "{}".format(self.gui.ui.nodesTableWidget.item(row, 0).text())
            subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(row, 1).text())
            self.__update_node_additional_info(node_id, subtask_id)

    def __close_button_clicked(self):
        self.gui.window.close()

    def __context_menu_requested(self, p):
        if self.gui.ui.nodesTableWidget.itemAt(p) is None:
            return
        row = self.gui.ui.nodesTableWidget.itemAt(p).row()
        id_item = self.gui.ui.nodesTableWidget.item(row, 1)
        subtask_id = "{}".format(id_item.text())
        id_item = self.gui.ui.nodesTableWidget.item(row, 3)
        subtask_status = "{}".format(id_item.text())
        menu = QMenu()
        self.subtaskContextMenuCustomizer = SubtaskContextMenuCustomizer(menu, self.logic, subtask_id, subtask_status)
        menu.popup(self.gui.ui.nodesTableWidget.viewport().mapToGlobal(p))
        menu.exec_()
