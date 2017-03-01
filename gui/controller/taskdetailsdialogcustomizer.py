import datetime
import logging

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMenu

from golem.task.taskstate import ComputerState
from gui.view.dialog import SubtaskDetailsDialog
from subtaskcontextmenucustomizer import SubtaskContextMenuCustomizer
from customizer import Customizer
from subtaskdetailsdialogcustomizer import SubtaskDetailsDialogCustomizer

from gui.view.subtasktableentry import SubtaskTableElem


logger = logging.getLogger("gui")


class SortingOrder(object):
    ascending = QtCore.Qt.AscendingOrder
    descending = QtCore.Qt.DescendingOrder


class TaskDetailsDialogCustomizer(Customizer):
    def __init__(self, gui, logic, task_desc):
        self.task_desc = task_desc
        self.subtask_table_elements = {}
        
        # which column use for sorting subtasks
        self.sorting = -1
        self.sorting_order = None
        Customizer.__init__(self, gui, logic)
        self.update_view(self.task_desc.task_state)

    def update_view(self, task_state):
        self.task_desc.task_state = task_state
        self.__update_data()

    def show_subtask_info_dialog(self, subtask_id):
        subtask = self.__get_subtask(subtask_id)
        if subtask is None:
            logger.error("There's no such subtask: {}".format(subtask_id))
            return
        dialog = SubtaskDetailsDialog(self.gui.window)
        SubtaskDetailsDialogCustomizer(dialog, self, subtask)
        dialog.show()

    def __get_subtask(self, subtask_id):
        for subtask in self.task_desc.task_state.subtask_states.itervalues():
            if subtask.subtask_id == subtask_id:
                return subtask
        return None

    def __update_data(self):
        self.gui.ui.totalTaskProgressBar.setProperty("value", int(self.task_desc.task_state.progress * 100))
        self.gui.ui.estimatedRemainingTimeLabel.setText(
            str(datetime.timedelta(seconds=self.task_desc.task_state.remaining_time)))
        self.gui.ui.elapsedTimeLabel.setText(
            str(datetime.timedelta(seconds=self.task_desc.task_state.elapsed_time)))

        for k in self.task_desc.task_state.subtask_states:
            if k not in self.subtask_table_elements:
                ss = self.task_desc.task_state.subtask_states[k]
                self.__add_node(ss.computer.node_name, ss.subtask_id, ss.subtask_status)

        for k, elem in self.subtask_table_elements.items():
            if elem.subtask_id in self.task_desc.task_state.subtask_states:
                ss = self.task_desc.task_state.subtask_states[elem.subtask_id]
                elem.update(ss.subtask_progress, ss.subtask_status, ss.subtask_rem_time)
            else:
                del self.subtask_table_elements[k]

    def _setup_connections(self):
        self.gui.ui.nodesTableWidget.cellClicked.connect(self.__nodes_table_row_clicked)
        self.gui.ui.nodesTableWidget.itemSelectionChanged.connect(self.__nodes_table_row_selected)
        self.gui.ui.nodesTableWidget.doubleClicked.connect(self.__nodes_table_row_double_clicked)
        self.gui.ui.nodesTableWidget.horizontalHeader().sectionClicked.connect(self.__header_clicked)
        self.gui.ui.nodesTableWidget.customContextMenuRequested.connect(self.__context_menu_requested)
        self.gui.ui.closeButton.clicked.connect(self.__close_button_clicked)

    def __header_clicked(self, column):
        if column == self.sorting:
            if self.sorting_order == SortingOrder.ascending:
                self.sorting_order = SortingOrder.descending
            else:
                self.sorting_order = SortingOrder.ascending
        else:
            self.sorting_order = SortingOrder.ascending
            self.sorting = column
        self.gui.ui.nodesTableWidget.sortItems(self.sorting, self.sorting_order)

    def __update_node_additional_info(self, node_name, subtask_id):
        if subtask_id in self.task_desc.task_state.subtask_states:
            ss = self.task_desc.task_state.subtask_states[subtask_id]
            comp = ss.computer

            if not isinstance(comp, ComputerState):
                raise TypeError("Incorrect computer type: {}. Should be ComputerState".format(type(comp)))

            self.gui.ui.nodeNameLabel.setText(node_name)
            self.gui.ui.nodeIpAddressLabel.setText(comp.ip_address)
            self.gui.ui.performanceLabel.setText("{}".format(comp.performance))
            self.gui.ui.subtaskDefinitionTextEdit.setPlainText(ss.subtask_definition)

    def __add_node(self, node_name, subtask_id, status):
        current_row_count = self.gui.ui.nodesTableWidget.rowCount()
        self.gui.ui.nodesTableWidget.insertRow(current_row_count)

        subtask_table_elem = SubtaskTableElem(node_name, subtask_id, status)

        for col in range(0, 4):
            self.gui.ui.nodesTableWidget.setItem(current_row_count, col, subtask_table_elem.get_column_item(col))

        self.gui.ui.nodesTableWidget.setCellWidget(current_row_count, 4,
                                                   subtask_table_elem.progressBarInBoxLayoutWidget)

        self.subtask_table_elements[subtask_id] = subtask_table_elem

        subtask_table_elem.update(0.0, "", 0.0)

        self.__update_node_additional_info(node_name, subtask_id)
        
        if self.sorting != -1 and self.sorting_order is not None:
            self.gui.ui.nodesTableWidget.sortItems(self.sorting, self.sorting_order)
            

    # SLOTS
    ###########################
    def __nodes_table_row_clicked(self, r, c):

        node_name = "{}".format(self.gui.ui.nodesTableWidget.item(r, 0).text())
        subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(r, 1).text())
        self.__update_node_additional_info(node_name, subtask_id)

    def __nodes_table_row_selected(self):
        if self.gui.ui.nodesTableWidget.selectedItems():
            row = self.gui.ui.nodesTableWidget.selectedItems()[0].row()
            node_name = "{}".format(self.gui.ui.nodesTableWidget.item(row, 0).text())
            subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(row, 1).text())
            self.__update_node_additional_info(node_name, subtask_id)

    def __nodes_table_row_double_clicked(self, m):
        row = m.row()
        subtask_id = "{}".format(self.gui.ui.nodesTableWidget.item(row, 1).text())
        self.show_subtask_info_dialog(subtask_id)

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
