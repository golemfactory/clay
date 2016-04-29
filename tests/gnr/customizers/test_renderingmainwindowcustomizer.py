import os
from mock import MagicMock, patch
from gnr.application import GNRGui
from gnr.ui.appmainwindow import AppMainWindow

from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from golem.tools.testdirfixture import TestDirFixture


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
        gnrgui.app.quit()
        gnrgui.app.deleteLater()
