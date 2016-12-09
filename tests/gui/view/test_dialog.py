import sys
from unittest import TestCase

from PyQt4.QtGui import QApplication, QMainWindow

from gui.view.dialog import PaymentsDialog, EnvironmentsDialog, NodeNameDialog, ChangeTaskDialog


class TestDialogs(TestCase):
    def test_dialogs(self):
        app = QApplication(sys.argv)
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
