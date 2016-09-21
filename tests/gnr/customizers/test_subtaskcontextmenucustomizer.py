from unittest import TestCase

from mock import Mock, patch

from golem.task.taskstate import SubtaskStatus, SubtaskState

from gnr.customizers.subtaskcontextmenucustomizer import SubtaskContextMenuCustomizer


class TestSubtaskContextMenuCustomizer(TestCase):
    @patch("gnr.customizers.subtaskcontextmenucustomizer.QAction")
    def test_restarted(self, mock_action):
        menu = SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.restarted)
        assert isinstance(menu, SubtaskContextMenuCustomizer)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.starting)
        mock_action.return_value.setEnabled.assert_called_with(True)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.waiting)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.failure)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.finished)
        mock_action.return_value.setEnabled.assert_called_with(True)
        SubtaskContextMenuCustomizer(Mock(), Mock(), "xxyyzz", SubtaskStatus.resent)
        mock_action.return_value.setEnabled.assert_called_with(False)