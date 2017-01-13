from unittest import TestCase

from mock import Mock, patch

from gui.controller.taskcontexmenucustomizer import TaskContextMenuCustomizer
from golem.task.taskstate import TaskStatus, TaskState
from apps.core.task.coretaskstate import TaskDesc

class TestTaskContextMenuCustomizer(TestCase):
    @patch("gui.controller.taskcontexmenucustomizer.QAction")
    def test_menu(self, mock_action):
        td = TaskDesc()
        TASK_ID = "TESTTTASK"
        td.definition.task_id = TASK_ID
        status = [TaskStatus.notStarted, TaskStatus.sending, TaskStatus.waiting,
                  TaskStatus.starting, TaskStatus.computing, TaskStatus.finished,
                  TaskStatus.finished, TaskStatus.aborted, TaskStatus.timeout,
                  TaskStatus.paused]
        menu = None
        for st in status:
            td.task_state.status = st
            menu = TaskContextMenuCustomizer(Mock(), Mock(), td)

        assert menu is not None
        menu._TaskContextMenuCustomizer__abort_task_triggered()
        menu.logic.abort_task.assert_called_with(TASK_ID)


        menu._TaskContextMenuCustomizer__restart_task_triggered()
        menu.logic.restart_task.assert_called_with(TASK_ID)


        menu._TaskContextMenuCustomizer__delete_task_triggered()
        menu.logic.delete_task.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__clone_task_triggered()
        menu.logic.clone_task.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__start_task_triggered()
        menu.logic.start_task.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__pause_task_triggered()
        menu.logic.pause_task.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__resume_task_triggered()
        menu.logic.resume_task.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__show_task_details_triggered()
        menu.logic.show_task_details.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__change_task_triggered()
        menu.logic.change_task.assert_called_with(TASK_ID)

        menu._TaskContextMenuCustomizer__show_result_triggered()
        menu.logic.show_task_result.assert_called_with(TASK_ID)