import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
if os.path.normpath(os.getcwd()) == os.path.normpath( os.path.join( os.environ.get('GOLEM'), "examples/gnr" ) ):
    genUiFiles( "ui" )

from RenderingApplicationLogic import RenderingApplicationLogic

from examples.gnr.ui.RenderingMainWindow import RenderingMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingMainWindowCustomizer import RenderingMainWindowCustomizer

from GNRstartApp import startApp

def main():

    if os.path.normpath(os.getcwd()) == os.path.normpath( os.path.join( os.environ.get('GOLEM'), "examples/gnr" ) ):
        logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingApplicationLogic()
    app     = GNRGui( logic, RenderingMainWindow )
    gui     = RenderingMainWindowCustomizer

    startApp( logic, app, gui, rendering = True )


from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
