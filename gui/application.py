import sys
from PyQt5 import QtCore
from os import path

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from golem.core.common import get_golem_path


class Gui:
    def __init__(self, app_logic, mainWindowClass):
        try:
            # Linux check might suffice if X11 was the only option available
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads)
        except Exception as ex:
            from sys import platform
            if platform != "win32":
                from logging import getLogger
                logger = getLogger("gui")
                logger.warning("Error occurred when setting up Qt: {}".format(ex))

        self.app = QApplication(sys.argv)
        app_icon = QIcon()
        icon_path = path.join(get_golem_path(), "gui", "view", "img")
        app_icon.addFile(path.join(icon_path, "favicon-32x32.png"), QSize(32, 32))
        app_icon.addFile(path.join(icon_path, "favicon-48x48.png"), QSize(48, 48))
        app_icon.addFile(path.join(icon_path, "favicon-256x256.png"), QSize(256, 256))
        self.app.setWindowIcon(app_icon)

        self.main_window = mainWindowClass()
        self.app_logic = app_logic

    def execute(self):
        self.main_window.show()
        self.main_window.window.logic_quit_func = self.app_logic.quit

    def get_main_window(self):
        return self.main_window
