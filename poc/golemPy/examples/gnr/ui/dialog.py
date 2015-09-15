from PyQt4.QtGui import QDialog

from gen.ui_save_keys_dialog import Ui_save_keys_dialog


class Dialog(object):
    """ Basic dialog ewindow extenstion, save specific given class as ui """
    def __init__(self, parent, ui_class):
        self.window = QDialog(parent)
        self.ui = ui_class()
        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()


class SaveKeysDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, Ui_save_keys_dialog)

