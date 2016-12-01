from PyQt4.QtGui import QDialog

from apps.core.gui.view.gen.ui_AddTaskResourcesDialog import Ui_AddTaskResourcesDialog
from gen.ui_ChangeTaskDialog import Ui_ChangeTaskDialog
from gen.ui_EnvironmentsDialog import Ui_EnvironmentsDialog
from gen.ui_GeneratingKeyWindow import Ui_generating_key_window
from gen.ui_IdentityDialog import Ui_identity_dialog
from gen.ui_NodeNameDialog import Ui_NodeNameDialog
from gen.ui_PaymentsDialog import Ui_PaymentsDialog
from gen.ui_SaveKeysDialog import Ui_SaveKeysDialog
from gen.ui_ShowTaskResourcesDialog import Ui_ShowTaskResourceDialog
from gen.ui_SubtaskDetailsDialog import Ui_SubtaskDetailsDialog
from gen.ui_TaskDetailsDialog import Ui_TaskDetailsDialog
from gen.ui_TestingTaskProgressDialog import Ui_testingTaskProgressDialog
from gui.view.gen.ui_UpdatingConfigDialog import Ui_updatingConfigDialog


class Dialog(object):
    """ Basic dialog window extension, save specific given class as ui """
    def __init__(self, parent, ui_class):
        self.window = QDialogPlus(parent)
        self.ui = ui_class()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()

    def close(self):
        try:
            self.ui.enable_close(True)
        except AttributeError:
            pass
        self.window.close()

class QDialogPlus(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.can_be_closed = True

    def closeEvent(self, event):
        if self.can_be_closed:
            event.accept()
        else:
            event.ignore()

    def enable_close(self, enable):
        self.can_be_closed = enable


# TASK INFO DIALOGS

class TaskDetailsDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_TaskDetailsDialog)


class SubtaskDetailsDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_SubtaskDetailsDialog)


# INFO DIALOGS


class PaymentsDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_PaymentsDialog)


# CONFIGURATION DIALOGS

class EnvironmentsDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_EnvironmentsDialog)


class IdentityDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_identity_dialog)


class GeneratingKeyWindow(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_generating_key_window)


class SaveKeysDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_SaveKeysDialog)


class UpdatingConfigDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_updatingConfigDialog)


class NodeNameDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_NodeNameDialog)


# ADDING TASK DIALOGS


class TestingTaskProgressDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_testingTaskProgressDialog)
        self.ui.progressBar.setRange(0, 0)

    def stop_progress_bar(self):
        self.ui.progressBar.setRange(0, 1)
        self.ui.progressBar.setVisible(False)


class AddTaskResourcesDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_AddTaskResourcesDialog)


class ShowTaskResourcesDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_ShowTaskResourceDialog)


class ChangeTaskDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_ChangeTaskDialog)

