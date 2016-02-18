import unittest
import tempfile
import os

from mock import Mock, patch

from gnr.customizers.customizer import Customizer


class TestCustomizer(unittest.TestCase):
    def test_init(self):
        customizer = Customizer(Mock(), Mock())
        self.assertIsInstance(customizer, Customizer)

    @patch("gnr.customizers.customizer.exec_cmd")
    @patch("gnr.customizers.customizer.is_windows")
    @patch("gnr.customizers.customizer.os")
    def test_show_file(self, mock_os, mock_is_windows, mock_exec):
        with tempfile.NamedTemporaryFile(prefix="golem", delete=False) as file_:
            file_name = file_.name
        print file_name
        try:
            mock_is_windows.return_value = True
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_exec.assert_not_called()
            mock_is_windows.return_value = False
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_exec.assert_called_with(["see", file_name], wait=False)
        finally:
            if os.path.isfile(file_name):
                os.remove(file_name)