import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
if os.path.normpath(os.getcwd()) == os.path.normpath(os.environ.get('GOLEM')):
    genUiFiles( "ui" )

from RenderingAdmApplicationLogic import RenderingAdmApplicationLogic
from GNRstartApp import startApp

from examples.gnr.ui.AdministrationMainWindow import AdministrationMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingAdmMainWindowCustomizer import RenderingAdmMainWindowCustomizer


def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingAdmApplicationLogic()
    app     = GNRGui( logic, AdministrationMainWindow )
    gui     = RenderingAdmMainWindowCustomizer

    startApp( logic, app, gui, rendering = True, startAddTaskClient = True, startAddTaskServer= True )

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
