import unittest
import unittest.mock as mock

from golem.task.taskstate import SubtaskStatus, SubtaskState

from gui.controller.subtaskcontextmenucustomizer import SubtaskContextMenuCustomizer


class TestSubtaskContextMenuCustomizer(unittest.TestCase):
    @mock.patch("gui.controller.subtaskcontextmenucustomizer.QAction")
    def test_restarted(self, mock_action):
        menu = SubtaskContextMenuCustomizer(mock.Mock(), mock.Mock(), "xxyyzz", SubtaskStatus.restarted)
        assert isinstance(menu, SubtaskContextMenuCustomizer)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(mock.Mock(), mock.Mock(), "xxyyzz", SubtaskStatus.starting)
        mock_action.return_value.setEnabled.assert_called_with(True)
        SubtaskContextMenuCustomizer(mock.Mock(), mock.Mock(), "xxyyzz", SubtaskStatus.downloading)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(mock.Mock(), mock.Mock(), "xxyyzz", SubtaskStatus.failure)
        mock_action.return_value.setEnabled.assert_called_with(False)
        SubtaskContextMenuCustomizer(mock.Mock(), mock.Mock(), "xxyyzz", SubtaskStatus.finished)
        mock_action.return_value.setEnabled.assert_called_with(True)
        SubtaskContextMenuCustomizer(mock.Mock(), mock.Mock(), "xxyyzz", SubtaskStatus.resent)
        mock_action.return_value.setEnabled.assert_called_with(False)
