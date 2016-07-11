import os
from unittest import TestCase

from mock import MagicMock, patch
from PIL import Image

from golem.task.taskstate import SubtaskState, SubtaskStatus
from golem.tools.testdirfixture import TestDirFixture

from gnr.application import GNRGui

from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer, subtasks_priority
from gnr.renderingtaskstate import RenderingTaskState
from gnr.ui.appmainwindow import AppMainWindow


class TestRenderingMainWindowCustomizer(TestDirFixture):
    @patch('gnr.customizers.gnrmainwindowcustomizer.QtCore')
    @patch('gnr.customizers.renderingmainwindowcustomizer.QtCore')
    @patch('gnr.customizers.gnrmainwindowcustomizer.QPalette')
    def test_preview(self, mock_palette, mock_core, mock_core2):
            customizer = RenderingMainWindowCustomizer(MagicMock(), MagicMock())
            self.assertTrue(os.path.isfile(customizer.preview_path))

    def test_folderTreeView(self):
        tmp_files = self.additional_dir_content([4, [3], [2]])
        gnrgui = GNRGui(MagicMock(), AppMainWindow)
        customizer = RenderingMainWindowCustomizer(gnrgui.get_main_window(), MagicMock())

        customizer.gui.ui.showResourceButton.click()
        customizer.current_task_highlighted = MagicMock()
        customizer.current_task_highlighted.definition.main_scene_file = tmp_files[0]
        customizer.current_task_highlighted.definition.resources = tmp_files
        customizer.gui.ui.showResourceButton.click()

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()

    def test_update_preview(self):
        gnrgui = GNRGui(MagicMock(), AppMainWindow)
        customizer = RenderingMainWindowCustomizer(gnrgui.get_main_window(), MagicMock())
        rts = RenderingTaskState()
        rts.definition.output_file = "bla"
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.outputFile.text() == "bla"
        assert not customizer.gui.ui.frameSlider.isVisible()
        assert customizer.last_preview_path == customizer.preview_path
        assert customizer.gui.ui.previewLabel.pixmap().width() == 297
        assert customizer.gui.ui.previewLabel.pixmap().height() == 200

        img = Image.new("RGB", (512, 512), "white")
        img_path = os.path.join(self.path, "image1.png")
        img.save(img_path)
        rts.task_state.extra_data = {"resultPreview": img_path}
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 200
        assert customizer.gui.ui.previewLabel.pixmap().height() == 200

        img = Image.new("RGB", (250, 500), "white")
        img.save(img_path)
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 100
        assert customizer.gui.ui.previewLabel.pixmap().height() == 200

        img = Image.new("RGB", (500, 250), "white")
        img.save(img_path)
        customizer.update_task_additional_info(rts)
        assert customizer.gui.ui.previewLabel.pixmap().width() == 300
        assert customizer.gui.ui.previewLabel.pixmap().height() == 150

        rts.definition.renderer = u"Blender"
        rts.definition.renderer_options = MagicMock()
        rts.definition.renderer_options.use_frames = True
        rts.definition.renderer_options.frames = range(10)
        rts.task_state.extra_data = {"resultPreview": [img_path]}
        customizer.update_task_additional_info(rts)

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()


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

