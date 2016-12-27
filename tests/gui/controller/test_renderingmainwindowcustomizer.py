import os
from unittest import TestCase

from mock import MagicMock, patch
from PIL import Image

from apps.core.task.gnrtaskstate import TaskDesc
from gui.controller.mainwindowcustomizer import MainWindowCustomizer
from gui.controller.previewcontroller import subtasks_priority
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition


from golem.task.taskstate import SubtaskState, SubtaskStatus
from golem.tools.testdirfixture import TestDirFixture

from gui.application import GNRGui
from gui.view.appmainwindow import AppMainWindow


class TestRenderingMainWindowCustomizer(TestDirFixture):

    def setUp(self):
        super(TestRenderingMainWindowCustomizer, self).setUp()
        self.logic = MagicMock()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestRenderingMainWindowCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    @patch('gui.controller.previewcontroller.QObject')
    @patch('gui.controller.mainwindowcustomizer.QObject')
    @patch('gui.controller.mainwindowcustomizer.QPalette')
    def test_preview(self, mock_palette, mock_object, mock_object2):
        customizer = MainWindowCustomizer(MagicMock(), MagicMock())
        self.assertTrue(os.path.isfile(customizer.preview_controller.preview_path))

    def test_folderTreeView(self):
        tmp_files = self.additional_dir_content([4, [3], [2]])
        customizer = MainWindowCustomizer(self.gnrgui.get_main_window(), MagicMock())

        customizer.gui.ui.showResourceButton.click()
        customizer.current_task_highlighted = MagicMock()
        customizer.current_task_highlighted.definition.main_scene_file = tmp_files[0]
        customizer.current_task_highlighted.definition.resources = tmp_files
        customizer.gui.ui.showResourceButton.click()

    def test_update_preview(self):
        customizer = MainWindowCustomizer(self.gnrgui.get_main_window(), MagicMock())
        rts = TaskDesc(definition_class=RenderingTaskDefinition)
        rts.definition.output_file = "bla"
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.outputFile.text() == "bla"
        assert not customizer.gui.ui.previewsSlider.isVisible()
        assert customizer.preview_controller.last_preview_path == customizer.preview_controller.preview_path
        assert customizer.gui.ui.previewLabel.pixmap().width() == 298
        assert customizer.gui.ui.previewLabel.pixmap().height() == 200

        img = Image.new("RGB", (250, 123), "white")
        img_path = os.path.join(self.path, "image1.png")
        img.save(img_path)
        rts.task_state.extra_data = {"resultPreview": img_path}
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 250
        assert customizer.gui.ui.previewLabel.pixmap().height() == 123

        img = Image.new("RGB", (301, 206), "white")
        img.save(img_path)
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 301
        assert customizer.gui.ui.previewLabel.pixmap().height() == 206

        rts.definition.task_type = u"Blender"
        rts.definition.options = MagicMock()
        rts.definition.options.use_frames = True
        rts.definition.options.frames = range(10)
        rts.task_state.outputs = ["result"] * 10
        rts.task_state.extra_data = {"resultPreview": [img_path]}
        customizer.update_task_additional_info(rts)

    @patch("gui.controller.customizer.QMessageBox")
    def test_show_task_result(self, mock_messagebox):
        customizer = MainWindowCustomizer(self.gnrgui.get_main_window(), MagicMock())
        td = TaskDesc()
        td.definition.task_type = "Blender"
        td.definition.options.use_frames = True
        td.definition.output_file = os.path.join(self.path, "output.png")
        td.task_state.outputs = [os.path.join(self.path, u"output0011.png"),
                                 os.path.join(self.path, u"output0014.png"),
                                 os.path.join(self.path, u"output0017.png")]
        td.definition.options.frames = [11, 14, 17]
        customizer.logic.get_task.return_value = td
        customizer.current_task_highlighted = td
        customizer.gui.ui.previewsSlider.setRange(1, 3)
        mock_messagebox.Critical = "CRITICAL"
        customizer.show_task_result("abc")
        expected_file = td.task_state.outputs[0]
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           expected_file + u" is not a file")
        customizer.gui.ui.previewsSlider.setValue(2)
        customizer.show_task_result("abc")
        expected_file = td.task_state.outputs[1]
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           expected_file + u" is not a file")
        customizer.gui.ui.previewsSlider.setValue(3)
        customizer.show_task_result("abc")
        expected_file = td.task_state.outputs[2]
        mock_messagebox.assert_called_with(mock_messagebox.Critical, "Error",
                                           expected_file + u" is not a file")

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
