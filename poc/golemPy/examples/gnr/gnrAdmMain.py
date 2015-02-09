import logging
import logging.config
import os
import sys

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )


from examples.gnr.GNRAdmApplicationLogic import GNRAdmApplicationLogic
from examples.gnr.Application import GNRGui



from examples.gnr.ui.MainWindow import GNRMainWindow
from examples.gnr.customizers.GNRAdministratorMainWindowCustomizer import GNRAdministratorMainWindowCustomizer
from GNRstartApp import startGNRApp

def main():
    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = GNRAdmApplicationLogic()
    app     = GNRGui( logic, GNRMainWindow )
    gui     = GNRAdministratorMainWindowCustomizer
    startGNRApp( logic, app, gui,startManager = True, startInfoServer = True )


main()