import sys
import logging
from PyQt4.QtGui import QApplication

logger = logging.getLogger(__name__)


class GNRGui:
    def __init__(self, app_logic, mainWindowClass):
        self.app = QApplication(sys.argv)
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
