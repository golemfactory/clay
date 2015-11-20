import sys
import os
import logging
import logging.config

sys.path.insert(0, os.environ.get('GOLEM'))

from tools.uigen import gen_ui_files
if os.path.normpath(os.getcwd()) == os.path.normpath(os.path.join(os.environ.get('GOLEM'), "examples/gnr")):
    gen_ui_files("ui")

from RenderingAdmApplicationLogic import RenderingAdmApplicationLogic
from GNRstartApp import start_app

from examples.gnr.ui.AdministrationMainWindow import AdministrationMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingAdmMainWindowCustomizer import RenderingAdmMainWindowCustomizer


def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingAdmApplicationLogic()
    app     = GNRGui(logic, AdministrationMainWindow)
    gui     = RenderingAdmMainWindowCustomizer

    start_app(logic, app, gui, rendering = True, start_add_task_client = False, start_add_task_server= False)

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
