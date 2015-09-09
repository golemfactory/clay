import sys
import logging
from PyQt4.QtGui import QApplication

logger = logging.getLogger(__name__)

class GNRGui:
    ############################
    def __init__(self, appLogic, mainWindowClass):
        self.app            = QApplication(sys.argv)
        self.mainWindow     = mainWindowClass()
        self.appLogic       = appLogic

    ############################
    def execute(self, using_qt4_reactor = True):
        self.mainWindow.show()
        if not using_qt4_reactor:
            res = self.app.exec_()
            try:
                self.appLogic.quit()
            except Exception as err:
                logger.error("{}".format(err))
            finally:
                sys.exit(res)

    ############################
    def getMainWindow(self):
        return self.mainWindow





