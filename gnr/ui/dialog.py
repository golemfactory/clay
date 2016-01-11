from PyQt4.QtGui import QDialog


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


class SaveKeysDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_save_keys_dialog import Ui_save_keys_dialog
        Dialog.__init__(self, parent, Ui_save_keys_dialog)


class PaymentsDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_payments_dialog import Ui_PaymentsDialog
        Dialog.__init__(self, parent, Ui_PaymentsDialog)


class TaskDetailsDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_TaskDetailsDialog import Ui_TaskDetailsDialog
        Dialog.__init__(self, parent, Ui_TaskDetailsDialog)


class SubtaskDetailsDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_TaskDetailsDialog import Ui_SubtaskDetailsDialog
        Dialog.__init__(self, parent, Ui_SubtaskDetailsDialog)


class ChangeTaskDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_ChangeTaskDialog import Ui_ChangeTaskDialog
        Dialog.__init__(self, parent, Ui_ChangeTaskDialog)


class StatusWindow(Dialog):
    def __init__(self, parent):
        from gen.ui_StatusWindow import Ui_StatusWindow
        Dialog.__init__(self, parent, Ui_StatusWindow)


class AboutWindow(Dialog):
    def __init__(self, parent):
        from gen.ui_AboutWindow import Ui_AboutWindow
        Dialog.__init__(self, parent, Ui_AboutWindow)


class ConfigurationDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_ConfigurationDialog import Ui_ConfigurationDialog
        Dialog.__init__(self, parent, Ui_ConfigurationDialog)


class EnvironmentsDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_EnvironmentsDialog import Ui_EnvironmentsDialog
        Dialog.__init__(self, parent, Ui_EnvironmentsDialog)


class IdentityDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_IdentityDialog import Ui_identity_dialog
        Dialog.__init__(self, parent, Ui_identity_dialog)


class AddTaskResourcesDialog(Dialog):
    def __init__(self, parent):
        from gen.ui_AddTaskResourcesDialog import Ui_AddTaskResourcesDialog
        Dialog.__init__(self, parent, Ui_AddTaskResourcesDialog)
        self.__init_folder_tree_view()
        self.__setup_connections()


class GeneratingKeyWindow(Dialog):
    def __init__(self, parent):
        from gen.ui_GeneratingKeyWindow import Ui_generating_key_window
        Dialog.__init__(self, parent, Ui_generating_key_window)