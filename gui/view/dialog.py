from PyQt5.QtWidgets import QDialog

from apps.core.gui.view.gen.ui_AddTaskResourcesDialog import Ui_AddTaskResourcesDialog
from gui.view.gen.ui_ChangeTaskDialog import Ui_ChangeTaskDialog
from gui.view.gen.ui_EnvironmentsDialog import Ui_EnvironmentsDialog
from gui.view.gen.ui_NodeNameDialog import Ui_NodeNameDialog
from gui.view.gen.ui_PaymentsDialog import Ui_PaymentsDialog
from gui.view.gen.ui_ShowTaskResourcesDialog import Ui_ShowTaskResourceDialog
from gui.view.gen.ui_SubtaskDetailsDialog import Ui_SubtaskDetailsDialog
from gui.view.gen.ui_TaskDetailsDialog import Ui_TaskDetailsDialog
from gui.view.gen.ui_TestingTaskProgressDialog import Ui_testingTaskProgressDialog
from gui.view.gen.ui_UpdatingConfigDialog import Ui_updatingConfigDialog


class Dialog(object):
    """ Basic dialog window extension, save specific given class as ui """
    def __init__(self, parent, ui_class):
        self.window = QDialogPlus(parent)
        self.ui = ui_class()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.open()

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

