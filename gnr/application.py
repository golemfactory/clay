import logging
import sys
from PyQt4 import QtCore
from os import path

from PyQt4.QtCore import QSize
from PyQt4.QtGui import QApplication, QIcon

from golem.core.common import get_golem_path

logger = logging.getLogger("gnr.app")


class GNRGui:
    def __init__(self, app_logic, mainWindowClass):
        try:
            # Linux check might suffice if X11 was the only option available
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads)
        except Exception:
            pass

        self.app = QApplication(sys.argv)
        app_icon = QIcon()
        icon_path = path.join(get_golem_path(), "gnr", "ui", "img")
        app_icon.addFile(path.join(icon_path, "favicon-32x32.png"), QSize(32, 32))
        app_icon.addFile(path.join(icon_path, "favicon-48x48.png"), QSize(48, 48))
        app_icon.addFile(path.join(icon_path, "favicon-256x256.png"), QSize(256, 256))
        self.app.setWindowIcon(app_icon)

        self.main_window = mainWindowClass()
        self.app_logic = app_logic

    def execute(self, using_qt4_reactor=True):
        self.main_window.show()

        if not using_qt4_reactor:
            res = self.app.exec_()
            try:
                self.app_logic.quit()
            except Exception as err:
                logger.error("{}".format(err))
            finally:
                sys.exit(res)
        else:
            self.main_window.window.logic_quit_func = self.app_logic.quit

    def get_main_window(self):
        return self.main_window
