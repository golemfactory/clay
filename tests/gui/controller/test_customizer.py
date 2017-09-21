import os
import tempfile
import unittest
import unittest.mock as mock

from gui.controller.customizer import Customizer


class TestCustomizer(unittest.TestCase):
    def test_init(self):
        customizer = Customizer(mock.Mock(), mock.Mock())
        self.assertIsInstance(customizer, Customizer)

    @mock.patch("gui.controller.customizer.subprocess")
    @mock.patch("gui.controller.customizer.is_osx")
    @mock.patch("gui.controller.customizer.is_windows")
    @mock.patch("gui.controller.customizer.os")
    def test_show_file(self, mock_os, mock_is_windows, mock_is_osx, mock_subprocess):
        with tempfile.NamedTemporaryFile(prefix="golem", delete=False) as file_:
            file_name = file_.name
        print(file_name)
        try:
            mock_is_windows.return_value = True
            mock_is_osx.return_value = False
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_subprocess.assert_not_called()

            mock_is_windows.return_value = False
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_subprocess.call.assert_called_with(["xdg-open", file_name])

            mock_is_osx.return_value = True
            Customizer.show_file(file_name)
            mock_os.startfile.assert_called_once_with(file_name)
            mock_subprocess.call.assert_called_with(["open", file_name])
        finally:
            if os.path.isfile(file_name):
                os.remove(file_name)

    @mock.patch('gui.controller.customizer.QMessageBox')
    def test_show_warning_window(self, mock_messagebox):
        mock_messagebox.return_value = mock_messagebox

        customizer = Customizer(mock.Mock(), mock.Mock())
        customizer.show_warning_window("Test warning message")

        assert mock_messagebox.exec_.called
