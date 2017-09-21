from PyQt5.QtWidgets import QApplication
import sys
import unittest
import unittest.mock as mock


class TestMainWindow(unittest.TestCase):

    def setUp(self):
        super(TestMainWindow, self).setUp()
        self.app = QApplication(sys.argv)

    def tearDown(self):
        super(TestMainWindow, self).tearDown()
        self.app.exit(0)
        self.app.deleteLater()

    @mock.patch("gui.view.mainwindow.QMessageBox")
    def test_exit(self, msg_box):

        msg_box.Yes = 1
        msg_box.No = 2
        msg_box.return_value = msg_box

        from gui.view.appmainwindow import AppMainWindow
        from gui.view.mainwindow import MainWindow

        window = AppMainWindow()
        assert isinstance(window.window, MainWindow)
        assert window.ui is not None

        event = mock.MagicMock()
        msg_box.exec_.return_value = msg_box.No

        window.window.closeEvent(event)
        assert event.ignore.called
        assert not event.accept.called

        event = mock.MagicMock()
        msg_box.exec_.return_value = msg_box.Yes

        window.window.closeEvent(event)
        assert not event.ignore.called
        assert event.accept.called
