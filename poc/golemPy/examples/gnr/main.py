import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from RenderingApplicationLogic import RenderingApplicationLogic

from examples.gnr.ui.RenderingMainWindow import RenderingMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingMainWindowCustomizer import RenderingMainWindowCustomizer

from GNRstartApp import startApp

def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingApplicationLogic()
    app     = GNRGui( logic, RenderingMainWindow )
    gui     = RenderingMainWindowCustomizer

    startApp( logic, app, gui )

main()
