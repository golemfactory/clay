import os

from mock import MagicMock, patch
from PIL import Image

from gnr.application import GNRGui
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingtaskstate import RenderingTaskState
from gnr.ui.appmainwindow import AppMainWindow
from golem.tools.testdirfixture import TestDirFixture


class TestRenderingMainWindowCustomizer(TestDirFixture):

    def setUp(self):
        super(TestRenderingMainWindowCustomizer, self).setUp()
        self.logic = MagicMock()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestRenderingMainWindowCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

    @patch('gnr.customizers.gnrmainwindowcustomizer.QtCore')
    @patch('gnr.customizers.renderingmainwindowcustomizer.QtCore')
    @patch('gnr.customizers.gnrmainwindowcustomizer.QPalette')
    def test_preview(self, mock_palette, mock_core, mock_core2):
        customizer = RenderingMainWindowCustomizer(MagicMock(), MagicMock())
        self.assertTrue(os.path.isfile(customizer.preview_path))

    def test_folderTreeView(self):
        tmp_files = self.additional_dir_content([4, [3], [2]])
        customizer = RenderingMainWindowCustomizer(self.gnrgui.get_main_window(), MagicMock())

        customizer.gui.ui.showResourceButton.click()
        customizer.current_task_highlighted = MagicMock()
        customizer.current_task_highlighted.definition.main_scene_file = tmp_files[0]
        customizer.current_task_highlighted.definition.resources = tmp_files
        customizer.gui.ui.showResourceButton.click()

        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

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
