from unittest import TestCase

from mock import Mock

from gnr.customizers.timehelper import get_subtask_hours


class TestTimeHelper(TestCase):
    def test_get_subtask_hours(self):
        gui = Mock()
        gui.ui.subtaskTimeoutHourSpinBox.value.return_value = 3
        gui.ui.subtaskTimeoutMinSpinBox.value.return_value = 20
        gui.ui.subtaskTimeoutSecSpinBox.value.return_value = 36
        self.assertAlmostEqual(get_subtask_hours(gui), 3.34, 2)
        gui.ui.subtaskTimeoutHourSpinBox.value.return_value = 0
        gui.ui.subtaskTimeoutMinSpinBox.value.return_value = 30
        gui.ui.subtaskTimeoutSecSpinBox.value.return_value = 0
        self.assertAlmostEqual(get_subtask_hours(gui), 0.5)
