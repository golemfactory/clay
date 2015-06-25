import logging
import logging.config
import os
import sys

sys.path.append(os.environ.get('GOLEM'))

from tools.UiGen import genUiFiles
genUiFiles("ui")


from examples.gnr.GNRAdmApplicationLogic import GNRAdmApplicationLogic
from examples.gnr.Application import GNRGui



from examples.gnr.ui.MainWindow import GNRMainWindow
from examples.gnr.customizers.GNRAdministratorMainWindowCustomizer import GNRAdministratorMainWindowCustomizer
from GNRstartApp import startApp

def main():
    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = GNRAdmApplicationLogic()
    app     = GNRGui(logic, GNRMainWindow)
    gui     = GNRAdministratorMainWindowCustomizer
    startApp(logic, app, gui,startManager = True, startInfoServer = True)

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
