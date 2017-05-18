from unittest import TestCase

from mock import Mock, patch

from golem.task.taskstate import SubtaskStatus, SubtaskState

from gui.controller.subtaskcontextmenucustomizer import SubtaskContextMenuCustomizer


class TestSubtaskContextMenuCustomizer(TestCase):
    @patch("gui.controller.subtaskcontextmenucustomizer.QAction")
    def test_restarted(self, mock_action):
        menu = SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.restarted)
        assert isinstance(menu, SubtaskContextMenuCustomizer)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.starting)
        mock_action.return_value.setEnabled.assert_called_with(True)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.downloading)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.failure)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.finished)
        mock_action.return_value.setEnabled.assert_called_with(True)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.resent)
        mock_action.return_value.setEnabled.assert_called_with(False)