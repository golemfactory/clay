from unittest import TestCase

from mock import MagicMock

from golem.task.taskstate import SubtaskState, SubtaskStatus
from golem.testutils import TestGui

from apps.core.task.gnrtaskstate import TaskDesc

from gui.controller.previewcontroller import subtasks_priority, PreviewController


class TestPriorites(TestCase):
    def test_subtask_priority(self):
        s_rst = SubtaskState()
        s_rst.subtask_status = SubtaskStatus.restarted
        s_fil = SubtaskState()
        s_fil.subtask_status = SubtaskStatus.failure
        s_rsd = SubtaskState()
        s_rsd.subtask_status = SubtaskStatus.resent
        s_fin = SubtaskState()
        s_fin.subtask_status = SubtaskStatus.finished
        s_sta = SubtaskState()
        s_sta.subtask_status = SubtaskStatus.starting
        s_wai = SubtaskState()
        s_wai.subtask_status = SubtaskStatus.waiting
        assert subtasks_priority(s_rst) > subtasks_priority(s_fin)
        assert subtasks_priority(s_fil) > subtasks_priority(s_fin)
        assert subtasks_priority(s_rsd) > subtasks_priority(s_fin)
        assert subtasks_priority(s_fin) > subtasks_priority(s_sta)
        assert subtasks_priority(s_fin) > subtasks_priority(s_wai)


class TestPreviewController(TestGui):
    def test_output_file(self):
        maincontroller = MagicMock()
        pc = PreviewController(self.gnrgui.get_main_window(), self.logic, maincontroller)
        td = TaskDesc()

        # Test output color
        pc.set_preview(td)
        assert pc.gui.ui.outputFile.styleSheet() == "color: black"
        files = self.additional_dir_content([3])
        td.definition.output_file = files[0]
        pc.set_preview(td)
        assert pc.gui.ui.outputFile.styleSheet() == "color: blue"

        td.task_state.outputs = files
        pc.maincontroller.current_task_highlighted = td
        pc.set_preview(td)
        pc.gui.ui.previewsSlider.setValue(1)
        assert pc.gui.ui.outputFile.text() == files[0]
        pc.gui.ui.previewsSlider.setRange(1, 6)
        pc.gui.ui.previewsSlider.setValue(4)
        assert pc.gui.ui.outputFile.text() == ""

    def test_pixmap(self):
        maincontroller = MagicMock()
        pc = PreviewController(self.gnrgui.get_main_window(), self.logic, maincontroller)
        td = TaskDesc()
        pc.set_preview(td)
        pc._PreviewController__pixmap_clicked(10, 10)
        pc.maincontroller.show_subtask_details_dialog.assert_not_called()

        pc.maincontroller.current_task_highlighted = td
        pc._PreviewController__pixmap_clicked(10, 10)
        pc.maincontroller.show_subtask_details_dialog.assert_not_called()

        td.definition.task_type = "TASKTYPE"
        td.definition.task_id = "XYZ"
        pc.logic.get_task.return_value = td

        pc._PreviewController__pixmap_clicked(10, 10)
        pc.maincontroller.show_subtask_details_dialog.assert_not_called()

        task_type_mock = MagicMock()
        pc.logic.get_task_type.return_value = task_type_mock
        task_type_mock.get_task_num_from_pixels.return_value = 1
        subtask_mock = MagicMock()
        subtask_mock.extra_data = {'start_task': 4, 'end_task': 5}
        subtask_mock.subtask_status = SubtaskStatus.finished
        td.task_state.subtask_states["abc"] = subtask_mock

        pc._PreviewController__pixmap_clicked(10, 10)
        pc.maincontroller.show_subtask_details_dialog.assert_not_called()

        pc._PreviewController__pixmap_clicked(0, 0)
        pc.maincontroller.show_subtask_details_dialog.assert_not_called()

        subtask_mock.extra_data = {'start_task': 1, 'end_task': 2}
        pc._PreviewController__pixmap_clicked(10, 10)
        pc.maincontroller.show_subtask_details_dialog.assert_called_with(subtask_mock)

        td.task_state.outputs = ["output1", "output2"]
        pc._PreviewController__pixmap_clicked(10, 10)
        assert pc.maincontroller.show_subtask_details_dialog.call_count == 2