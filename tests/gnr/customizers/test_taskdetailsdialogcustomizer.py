from unittest import TestCase

from golem.task.taskstate import SubtaskState, SubtaskStatus

from apps.rendering.task.renderingtaskstate import RenderingTaskState

from gui.application import GNRGui

from gnr.customizers.taskdetailsdialogcustomizer import SortingOrder, TaskDetailsDialogCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.dialog import TaskDetailsDialog


class TestTaskDetailsDialogCustomizer(TestCase):

    def setUp(self):
        super(TestTaskDetailsDialogCustomizer, self).setUp()
        self.logic = RenderingApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestTaskDetailsDialogCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    def test_sorting(self):
        task_dialog = TaskDetailsDialog(self.gnrgui.main_window.window)
        task_state = RenderingTaskState()
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
