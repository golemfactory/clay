from PyQt4.QtGui import QDialog

from gen.ui_AddTaskResourcesDialog import Ui_AddTaskResourcesDialog
from gen.ui_BlenderRenderDialog import Ui_BlenderRenderDialog
from gen.ui_ChangeTaskDialog import Ui_ChangeTaskDialog
from gen.ui_ConfigurationDialog import Ui_ConfigurationDialog
from gen.ui_EnvironmentsDialog import Ui_EnvironmentsDialog
from gen.ui_GeneratingKeyWindow import Ui_generating_key_window
from gen.ui_IdentityDialog import Ui_identity_dialog
from gen.ui_InfoTaskDialog import Ui_InfoTaskDialog
from gen.ui_LuxRenderDialog import Ui_LuxRenderDialog
from gen.ui_NewTaskDialog import Ui_NewTaskDialog
from gen.ui_payments_dialog import Ui_PaymentsDialog
from gen.ui_PbrtDialog import Ui_PbrtDialog
from gen.ui_PbrtTaskDialog import Ui_PbrtTaskDialog
from gen.ui_RenderingNewTaskDialog import Ui_RenderingNewTaskDialog
from gen.ui_save_keys_dialog import Ui_save_keys_dialog
from gen.ui_ShowTaskResourcesDialog import Ui_ShowTaskResourceDialog
from gen.ui_SubtaskDetailsDialog import Ui_SubtaskDetailsDialog
from gen.ui_TaskDetailsDialog import Ui_TaskDetailsDialog
from gen.ui_TestingTaskProgressDialog import Ui_testingTaskProgressDialog
from gen.ui_ThreeDSMaxDialog import Ui_ThreeDSMaxDialog
from gen.ui_UpdateOtherGolemsDialog import Ui_UpdateOtherGolemsDialog
from gen.ui_VRayDialog import Ui_VRayDialog


class Dialog(object):
    """ Basic dialog window extenstion, save specific given class as ui """
    def __init__(self, parent, ui_class):
        self.window = QDialog(parent)
        self.ui = ui_class()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()

    def close(self):
        self.window.close()


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

class ConfigurationDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_ConfigurationDialog)


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
        Dialog.__init__(self, parent, Ui_save_keys_dialog)


# ADDING TASK DIALOGS

class RenderingNewTaskDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_RenderingNewTaskDialog)


class NewTaskDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_NewTaskDialog)


class TestingTaskProgressDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_testingTaskProgressDialog)


class AddTaskResourcesDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_AddTaskResourcesDialog)


class ShowTaskResourcesDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_ShowTaskResourceDialog)


class ChangeTaskDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_ChangeTaskDialog)


# TEST TASK DIALOGS

class InfoTaskDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_InfoTaskDialog)


class UpdateOtherGolemsDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_UpdateOtherGolemsDialog)


# RENDERER DIALOGS

class BlenderRenderDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_BlenderRenderDialog)


class LuxRenderDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_LuxRenderDialog)


class PbrtDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_PbrtDialog)


class PbrtTaskDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_PbrtTaskDialog)


class ThreeDSMaxDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_ThreeDSMaxDialog)


class VRayDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_VRayDialog)
