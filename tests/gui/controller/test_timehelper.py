from unittest import TestCase

from mock import Mock

from gui.controller.timehelper import get_subtask_hours, get_time_values


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
        
        gui.ui.fullTaskTimeoutHourSpinBox.value.return_value = 2
        gui.ui.fullTaskTimeoutMinSpinBox.value.return_value = 30
        gui.ui.fullTaskTimeoutSecSpinBox.value.return_value = 45
    
        gui.ui.subtaskTimeoutHourSpinBox.value.return_value = 3
        gui.ui.subtaskTimeoutMinSpinBox.value.return_value = 15
        gui.ui.subtaskTimeoutSecSpinBox.value.return_value = 45
    
        full_tt, sub_tt = get_time_values(gui)
        self.assertTrue(full_tt == 9045)
        self.assertTrue(sub_tt == 11745)
