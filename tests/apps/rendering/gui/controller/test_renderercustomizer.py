from mock import Mock

from apps.rendering.gui.controller.renderercustomizer import RendererCustomizer

from golem.testutils import TestGui


class TestRendererCustomizer(TestGui):

    class TestRC(RendererCustomizer):
        def get_task_name(self):
            return "TESTRC"

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