from mock import Mock, patch

from apps.rendering.gui.controller.renderercustomizer import (RendererCustomizer,
                                                              FrameRendererCustomizer)
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from apps.rendering.task.framerenderingtask import FrameRendererOptions

from golem.testutils import TestGui


class TestRendererCustomizer(TestGui):

    class TestRC(RendererCustomizer):
        def get_task_name(self):
            return "TESTRC"

    def test_get_task_name(self):
        gui = self.gui.get_main_window()
        with self.assertRaises(NotImplementedError):
            rc = RendererCustomizer(gui, self.logic)

    def test_add_ext_to_out_filename(self):
        gui = self.gui.get_main_window()
        gui.ui = Mock()

        controller = TestRendererCustomizer.TestRC(gui, self.logic)
        assert isinstance(controller, RendererCustomizer)

        # Empty output file
        gui.ui.outputFormatsComboBox.itemText.return_value = "PNG"
        gui.ui.outputFileLineEdit.text.return_value = ""
        assert controller._add_ext_to_out_filename() == ""

        # Output file without extension
        gui.ui.outputFormatsComboBox.findText.return_value = -1
        gui.ui.outputFileLineEdit.text.return_value = "filename"
        controller._add_ext_to_out_filename()
        gui.ui.outputFileLineEdit.setText.assert_called_with(u"filename.PNG")

        # Output file with proper extension
        gui.ui.outputFormatsComboBox.findText.return_value = 1
        gui.ui.outputFileLineEdit.text.return_value = "filename.PNG"
        controller._add_ext_to_out_filename()
        gui.ui.outputFileLineEdit.setText.assert_called_with(u"filename.PNG")

        # Output file with extension to replace
        gui.ui.outputFormatsComboBox.itemText.return_value = "EXR"
        gui.ui.outputFormatsComboBox.findText.return_value = 1
        gui.ui.outputFileLineEdit.text.return_value = "filename.PNG"
        controller._add_ext_to_out_filename()
        gui.ui.outputFileLineEdit.setText.assert_called_with(u"filename.EXR")

        #Output file with extension that should not be replaced
        gui.ui.outputFormatsComboBox.itemText.return_value = "EXR"
        gui.ui.outputFormatsComboBox.findText.return_value = -1
        gui.ui.outputFileLineEdit.text.return_value = "filename.filename.AND"
        controller._add_ext_to_out_filename()
        gui.ui.outputFileLineEdit.setText.assert_called_with(u"filename.filename.AND.EXR")

    def test_load_task_definition(self):
        gui = self.gui.get_main_window()
        gui.ui = Mock()

        controller = TestRendererCustomizer.TestRC(gui, self.logic)

        assert isinstance(controller, RendererCustomizer)
        task_def = RenderingTaskDefinition()
        files = self.additional_dir_content([1, [2]])
        task_def.resources = files
        task_def.main_scene_file = files[2]
        self.logic.dir_manager.root_path = self.path
        controller.load_task_definition(task_def)
        assert task_def.resources == files[:2]

    def test_change_options(self):
        gui = self.gui.get_main_window()
        gui.ui = Mock()

        controller = TestRendererCustomizer.TestRC(gui, self.logic)
        controller._change_options()

    @patch('apps.rendering.gui.controller.renderercustomizer.QFileDialog')
    def test_choose_main_file_button_clicked(self, file_dialog_mock):
        gui = self.gui.get_main_window()
        gui.ui = Mock()
        self.logic.dir_manager.root_path = self.path

        controller = TestRendererCustomizer.TestRC(gui, self.logic)
        file_dialog_mock.getOpenFileName.return_value = "result file name", 0
        controller._choose_main_scene_file_button_clicked()
        controller.gui.ui.mainSceneFileLineEdit.setText.assert_called_with("result file name")

    @patch('apps.rendering.gui.controller.renderercustomizer.QFileDialog')
    def test_choose_output_file_button_clicked(self, file_dialog_mock):
        gui = self.gui.get_main_window()
        gui.ui = Mock()
        self.logic.dir_manager.root_path = self.path

        controller = TestRendererCustomizer.TestRC(gui, self.logic)
        file_dialog_mock.getSaveFileName.return_value = "", 0
        controller._choose_output_file_button_clicked()
        controller.logic.task_settings_changed.assert_not_called()
        controller.gui.ui.outputFileLineEdit.setText.assert_not_called()

        file_dialog_mock.getSaveFileName.return_value = "result file name", 0
        controller._choose_output_file_button_clicked()
        controller.gui.ui.outputFileLineEdit.setText.assert_called_with("result file name")


class TestFrameRendererCustomizer(TestGui):
    class TestFRC(FrameRendererCustomizer):
        def get_task_name(self):
            return "FRAMETESTRC"

    def test_frames_from_options(self):
        gui = self.gui.get_main_window()
        gui.ui = Mock()

        controller = TestFrameRendererCustomizer.TestFRC(gui, self.logic)
        controller.options = FrameRendererOptions()
        controller.options.use_frames = False
        controller._set_frames_from_options()
        controller.gui.ui.framesLineEdit.setText.assert_called_with("")
        controller.options.use_frames = True
        controller.options.frames = range(3, 7)
        controller._set_frames_from_options()
        controller.gui.ui.framesLineEdit.setText.assert_called_with("3-6")

    def test_frames_check_box_changed(self):
        gui = self.gui.get_main_window()
        gui.ui = Mock()

        controller = TestFrameRendererCustomizer.TestFRC(gui, self.logic)
        gui.ui.framesCheckBox.isChecked.return_value = False

        prev_call_count = controller.gui.ui.framesLineEdit.setText.call_count
        controller._frames_check_box_changed()
        assert controller.gui.ui.framesLineEdit.setText.call_count == prev_call_count

        gui.ui.framesCheckBox.isChecked.return_value = True
        controller._frames_check_box_changed()
        assert controller.gui.ui.framesLineEdit.setText.call_count == prev_call_count + 1