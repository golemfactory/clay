import os
import subprocess

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QMessageBox

from golem.core.simpleexccmd import is_windows

SETTINGS_FILE = "gui_settings.ini"


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
            opener = "xdg-open"
            subprocess.call([opener, file_name])

    @staticmethod
    def show_error_window(text):
        ms_box = QMessageBox(QMessageBox.Critical, "Error", u"{}".format(text))
        ms_box.exec_()
        ms_box.show()

    @staticmethod
    def show_warning_window(text):
        ms_box = QMessageBox(QMessageBox.Warning, "Warning", u"{}".format(text))
        ms_box.exec_()
        ms_box.show()

    def save_setting(self, name, value, sync=False):
        settings = self._get_settings()
        settings.setValue(name, value)
        if sync:
            settings.sync()

    def load_setting(self, name, default):
        settings = self._get_settings()
        return settings.value(name, default)

    def _get_settings(self):
        settings_path = os.path.join(self.logic.dir_manager.root_path,
                                     SETTINGS_FILE)
        return QSettings(settings_path, QSettings.IniFormat)
