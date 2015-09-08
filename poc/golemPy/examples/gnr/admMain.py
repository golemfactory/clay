import sys
import os
import logging
import logging.config

sys.path.append(os.environ.get('GOLEM'))

from tools.uigen import gen_ui_files
if os.path.normpath(os.getcwd()) == os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/gnr")):
    gen_ui_files("ui")

from RenderingAdmApplicationLogic import RenderingAdmApplicationLogic
from GNRstartApp import startApp

from examples.gnr.ui.AdministrationMainWindow import AdministrationMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingAdmMainWindowCustomizer import RenderingAdmMainWindowCustomizer


def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingAdmApplicationLogic()
    app     = GNRGui(logic, AdministrationMainWindow)
    gui     = RenderingAdmMainWindowCustomizer

    startApp(logic, app, gui, rendering = True, startAddTaskClient = False, startAddTaskServer= False)

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
