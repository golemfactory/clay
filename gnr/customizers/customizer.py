import os

from PyQt4.QtGui import QMessageBox

from golem.core.simpleexccmd import is_windows, exec_cmd


class Customizer(object):

    def __init__(self, gui, logic):
        self.gui = gui
        self.logic = logic

        self.load_data()
        self._setup_connections()

    def _setup_connections(self):
        pass

    def load_data(self):
        pass

    @staticmethod
    def show_file(file_name):
        """ Open file with given using specific program that is connected with this file
        extension
        :param file_name: file that should be opened
        """
        if is_windows():
            os.startfile(file_name)
        else:
            opener = "see"
            exec_cmd([opener, file_name], wait=False)

    @staticmethod
    def show_error_window(text):

        ms_box = QMessageBox(QMessageBox.Critical, "Error", text)
        ms_box.exec_()
        ms_box.show()
