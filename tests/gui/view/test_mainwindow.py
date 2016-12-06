import sys
from unittest import TestCase

from mock import MagicMock, patch
from PyQt4.QtGui import QApplication

from gui.view.mainwindow import GNRMainWindow, MainWindow


class TestMainWindow(TestCase):
    @patch("gui.view.mainwindow.QMessageBox")
    def test_gnr_main_window(self, mock_message_box):
        app = QApplication(sys.argv)
        window = GNRMainWindow()
        assert isinstance(window.window, MainWindow)
        assert window.ui is not None
        window.show()
        event = MagicMock()
        window.window.closeEvent(event)
        mock_message_box.Yes = "yes"
        mock_message_box.question.return_value = mock_message_box.Yes
        window.window.closeEvent(event)
        event.accept.assert_called_with()
