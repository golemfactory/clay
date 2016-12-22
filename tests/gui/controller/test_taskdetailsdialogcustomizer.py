from PyQt4.QtCore import QPoint

from golem.task.taskstate import SubtaskState, SubtaskStatus
from golem.tools.assertlogs import LogTestCase

from apps.core.task.gnrtaskstate import TaskDesc

from gui.application import GNRGui
from gui.controller.taskdetailsdialogcustomizer import SortingOrder, TaskDetailsDialogCustomizer, logger
from gui.applicationlogic import GNRApplicationLogic
from gui.view.appmainwindow import AppMainWindow
from gui.view.dialog import TaskDetailsDialog


class TestTaskDetailsDialogCustomizer(LogTestCase):

    def setUp(self):
        super(TestTaskDetailsDialogCustomizer, self).setUp()
        self.logic = GNRApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestTaskDetailsDialogCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def __init_basic_customizer(self):
        task_dialog = TaskDetailsDialog(self.gnrgui.main_window.window)
        task_state = TaskDesc()
        ss1 = SubtaskState()
        ss1.subtask_id = "abc"
        ss1.computer.node_name ="ABC"
        ss1.computer.ip_address = "10.10.10.10"
        ss1.computer.performance = "1000"
        ss1.subtask_definition = "DEF 1"
        ss1.subtask_status = SubtaskStatus.waiting
        ss2 = SubtaskState()
        ss2.subtask_id = "def"
        ss2.computer.node_name = "DEF"
        ss2.computer.ip_address = "10.10.10.20"
        ss2.computer.performance = "2000"
        ss2.subtask_definition = "DEF 2"
        ss2.subtask_status = SubtaskStatus.starting
        ss3 = SubtaskState()
        ss3.subtask_id = "xyz"
        ss3.computer.node_name = "XYZ"
        ss3.computer.ip_address = "10.10.10.30"
        ss3.computer.performance = "3000"
        ss3.subtask_definition = "DEF 3"
        ss3.subtask_status = SubtaskStatus.finished
        task_state.task_state.subtask_states["abc"] = ss1
        task_state.task_state.subtask_states["def"] = ss2
        task_state.task_state.subtask_states["xyz"] = ss3
        task_state.task_state.progress = 0.33
        task_state.task_state.remaining_time = 34
        task_state.task_state.elapsed_time = 12
        customizer = TaskDetailsDialogCustomizer(task_dialog, self.logic, task_state)
        return customizer

    def test_sorting(self):
        task_dialog = TaskDetailsDialog(self.gnrgui.main_window.window)
        task_state = TaskDesc()
        customizer = TaskDetailsDialogCustomizer(task_dialog, self.logic, task_state)
        assert customizer.sorting == -1
        assert customizer.sorting_order is None
        task_state.task_state.progress = 0.33
        task_state.task_state.remaining_time = 34
        task_state.task_state.elapsed_time = 12
        ss1 = SubtaskState()
        ss1.computer.node_name = "ABC"
        ss1.subtask_id = "def"
        ss1.subtask_status = SubtaskStatus.finished
        task_state.task_state.subtask_states['def'] = ss1
        ss2 = SubtaskState()
        ss2.computer.node_name = "DEF"
        ss2.subtask_id = "abc"
        ss2.subtask_status = SubtaskStatus.finished
        task_state.task_state.subtask_states['abc'] = ss2
        customizer.update_view(task_state.task_state)
        assert customizer.sorting == -1
        assert customizer.sorting_order is None
        assert len(customizer.subtask_table_elements) == 2
        ids = [str(customizer.gui.ui.nodesTableWidget.item(i, 1).text()) for i in range(2)]
        assert 'def' in ids
        assert 'abc' in ids

        customizer._TaskDetailsDialogCustomizer__header_clicked(1)
        assert customizer.sorting == 1
        assert customizer.sorting_order == SortingOrder.ascending
        assert len(customizer.subtask_table_elements) == 2
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 0).text()) == "DEF"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 0).text()) == "ABC"
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 1).text()) == "abc"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 1).text()) == "def"

        customizer._TaskDetailsDialogCustomizer__header_clicked(1)
        assert customizer.sorting == 1
        assert customizer.sorting_order == SortingOrder.descending
        assert len(customizer.subtask_table_elements) == 2
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 0).text()) == "ABC"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 0).text()) == "DEF"
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 1).text()) == "def"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 1).text()) == "abc"

        ss3 = SubtaskState()
        ss3.computer.node_name = "FGH"
        ss3.subtask_id = "fgh"
        ss3.subtask_status = SubtaskStatus.finished
        task_state.task_state.subtask_states['fgh'] = ss3
        customizer.update_view(task_state.task_state)

        assert customizer.sorting == 1
        assert customizer.sorting_order == SortingOrder.descending
        assert len(customizer.subtask_table_elements) == 3
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 0).text()) == "FGH"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 0).text()) == "ABC"
        assert str(customizer.gui.ui.nodesTableWidget.item(2, 0).text()) == "DEF"
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 1).text()) == "fgh"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 1).text()) == "def"
        assert str(customizer.gui.ui.nodesTableWidget.item(2, 1).text()) == "abc"

        customizer._TaskDetailsDialogCustomizer__header_clicked(0)
        assert customizer.sorting == 0
        assert customizer.sorting_order == SortingOrder.ascending
        assert len(customizer.subtask_table_elements) == 3
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 0).text()) == "ABC"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 0).text()) == "DEF"
        assert str(customizer.gui.ui.nodesTableWidget.item(2, 0).text()) == "FGH"
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 1).text()) == "def"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 1).text()) == "abc"
        assert str(customizer.gui.ui.nodesTableWidget.item(2, 1).text()) == "fgh"

        customizer._TaskDetailsDialogCustomizer__header_clicked(0)
        assert customizer.sorting == 0
        assert customizer.sorting_order == SortingOrder.descending
        assert len(customizer.subtask_table_elements) == 3
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 0).text()) == "FGH"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 0).text()) == "DEF"
        assert str(customizer.gui.ui.nodesTableWidget.item(2, 0).text()) == "ABC"
        assert str(customizer.gui.ui.nodesTableWidget.item(0, 1).text()) == "fgh"
        assert str(customizer.gui.ui.nodesTableWidget.item(1, 1).text()) == "abc"
        assert str(customizer.gui.ui.nodesTableWidget.item(2, 1).text()) == "def"

    def test_subtask_dialog(self):
        customizer = self.__init_basic_customizer()
        with self.assertNoLogs(logger, level="WARNING"):
            customizer.show_subtask_info_dialog("xyz")
        with self.assertLogs(logger, level="WARNING"):
            customizer.show_subtask_info_dialog("NOTEXISTING")

    def test_slots(self):
        customizer = self.__init_basic_customizer()
        customizer._TaskDetailsDialogCustomizer__header_clicked(1)
        customizer._TaskDetailsDialogCustomizer__nodes_table_row_clicked(1, 2)
        assert customizer.gui.ui.nodeNameLabel.text() == "DEF"
        assert customizer.gui.ui.nodeIpAddressLabel.text() == "10.10.10.20"
        assert customizer.gui.ui.performanceLabel.text() == "2000"
        assert customizer.gui.ui.subtaskDefinitionTextEdit.toPlainText() == "DEF 2"
        customizer._TaskDetailsDialogCustomizer__nodes_table_row_clicked(2, 1)
        assert customizer.gui.ui.nodeNameLabel.text() == "XYZ"
        assert customizer.gui.ui.nodeIpAddressLabel.text() == "10.10.10.30"
        assert customizer.gui.ui.performanceLabel.text() == "3000"
        assert customizer.gui.ui.subtaskDefinitionTextEdit.toPlainText() == "DEF 3"
        customizer._TaskDetailsDialogCustomizer__nodes_table_row_clicked(0, 3)
        assert customizer.gui.ui.nodeNameLabel.text() == "ABC"
        assert customizer.gui.ui.nodeIpAddressLabel.text() == "10.10.10.10"
        assert customizer.gui.ui.performanceLabel.text() == "1000"
        assert customizer.gui.ui.subtaskDefinitionTextEdit.toPlainText() == "DEF 1"
        customizer.gui.ui.nodesTableWidget.selectRow(1)
        assert customizer.gui.ui.nodeNameLabel.text() == "DEF"
        assert customizer.gui.ui.nodeIpAddressLabel.text() == "10.10.10.20"
        assert customizer.gui.ui.performanceLabel.text() == "2000"
        assert customizer.gui.ui.subtaskDefinitionTextEdit.toPlainText() == "DEF 2"
        customizer.gui.ui.nodesTableWidget.selectRow(0)
        assert customizer.gui.ui.nodeNameLabel.text() == "ABC"
        assert customizer.gui.ui.nodeIpAddressLabel.text() == "10.10.10.10"
        assert customizer.gui.ui.performanceLabel.text() == "1000"
        assert customizer.gui.ui.subtaskDefinitionTextEdit.toPlainText() == "DEF 1"
        customizer.gui.ui.nodesTableWidget.selectRow(2)
        assert customizer.gui.ui.nodeNameLabel.text() == "XYZ"
        assert customizer.gui.ui.nodeIpAddressLabel.text() == "10.10.10.30"
        assert customizer.gui.ui.performanceLabel.text() == "3000"
        assert customizer.gui.ui.subtaskDefinitionTextEdit.toPlainText() == "DEF 3"
        customizer._TaskDetailsDialogCustomizer__context_menu_requested(QPoint(0, 0))

        customizer._TaskDetailsDialogCustomizer__close_button_clicked()