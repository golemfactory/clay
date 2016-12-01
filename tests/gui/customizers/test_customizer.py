import unittest
import tempfile
import os

from mock import Mock, patch

from gui.controller.customizer import Customizer


class TestCustomizer(unittest.TestCase):
    def test_init(self):
        customizer = Customizer(Mock(), Mock())
        self.assertIsInstance(customizer, Customizer)

    @patch("gui.controller.customizer.subprocess")
    @patch("gui.controller.customizer.is_windows")
    @patch("gui.controller.customizer.os")
    def test_show_file(self, mock_os, mock_is_windows, mock_subprocess):
        with tempfile.NamedTemporaryFile(prefix="golem", delete=False) as file_:
            file_name = file_.name
        print file_name
        try:
            mock_is_windows.return_value = True
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_subprocess.assert_not_called()
            mock_is_windows.return_value = False
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_subprocess.call.assert_called_with(["xdg-open", file_name])
        finally:
            if os.path.isfile(file_name):
                os.remove(file_name)
