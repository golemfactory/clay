import unittest
import os
from mock import MagicMock, patch

from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer


class TestRenderingMainWindowCustomizer(unittest.TestCase):

    @patch('gnr.customizers.gnrmainwindowcustomizer.QtCore')
    @patch('gnr.customizers.renderingmainwindowcustomizer.QtCore')
    @patch('gnr.customizers.gnrmainwindowcustomizer.QPalette')
    def test_preview(self, mock_palette, mock_core, mock_core2):
            customizer = RenderingMainWindowCustomizer(MagicMock(), MagicMock())
            self.assertTrue(os.path.isfile(customizer.preview_path))

