import sys
from unittest import TestCase

from mock import MagicMock, patch
from PyQt4.QtGui import QApplication

from gui.view.mainwindow import MainWindow
from gui.view.appmainwindow import AppMainWindow


class TestMainWindow(TestCase):

    def setUp(self):
        super(TestMainWindow, self).setUp()
        self.app = QApplication(sys.argv)

    def tearDown(self):
        super(TestMainWindow, self).tearDown()
        self.app.exit(0)
        self.app.deleteLater()

    @patch("gui.view.mainwindow.QMessageBox")
    def test_g_main_window(self, mock_message_box):
        window = AppMainWindow()
        assert isinstance(window.window, MainWindow)
        assert window.ui is not None
        window.show()
        event = MagicMock()
        window.window.closeEvent(event)
        mock_message_box.Yes = "yes"
        mock_message_box.question.return_value = mock_message_box.Yes
        window.window.closeEvent(event)
        event.accept.assert_called_with()
