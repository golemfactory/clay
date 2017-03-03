import sys
from unittest import TestCase

from PyQt5.QtWidgets import QApplication, QMainWindow

from gui.view.dialog import PaymentsDialog, EnvironmentsDialog, NodeNameDialog, ChangeTaskDialog


class TestDialogs(TestCase):

    def setUp(self):
        super(TestDialogs, self).setUp()
        self.app = QApplication(sys.argv)

    def tearDown(self):
        super(TestDialogs, self).tearDown()
        self.app.exit(0)
        self.app.deleteLater()

    def test_dialogs(self):
        window = QMainWindow()
        PaymentsDialog(window)
        EnvironmentsDialog(window)
        NodeNameDialog(window)
        dialog = ChangeTaskDialog(window)
        dialog.can_be_closed = False
        dialog.close()
        dialog.can_be_closed = True
        dialog.close()
        window.close()
