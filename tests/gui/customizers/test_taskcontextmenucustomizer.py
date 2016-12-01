from unittest import TestCase

from mock import Mock, patch

from gui.controller.taskcontexmenucustomizer import TaskContextMenuCustomizer
from golem.task.taskstate import TaskStatus, TaskState


class TestTaskContextMenuCustomizer(TestCase):
    @patch("gui.controller.taskcontexmenucustomizer.QAction")
    def test_menu(self, mock_action):
        ts = Mock()
        ts.task_state = TaskState()
        status = [TaskStatus.notStarted, TaskStatus.sending, TaskStatus.waiting,
                  TaskStatus.starting, TaskStatus.computing, TaskStatus.finished,
                  TaskStatus.finished, TaskStatus.aborted, TaskStatus.timeout,
                  TaskStatus.paused]
        for st in status:
            ts.task_state.status = st
            menu = TaskContextMenuCustomizer(Mock(), Mock(), ts)
