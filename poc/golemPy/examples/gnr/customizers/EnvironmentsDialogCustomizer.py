from examples.gnr.ui.EnvironmentsDialog import EnvironmentsDialog
from examples.gnr.ui.EnvTableElem import EnvTableElem
from PyQt4.QtGui import QTableWidgetItem

import logging

logger = logging.getLogger(__name__)

class EnvironmentsDialogCustomizer:
    #############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, EnvironmentsDialog )

        self.gui    = gui
        self.logic  = logic

        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        environments = self.logic.getEnvironments()
        for env in environments:
            currentRowCount = self.gui.ui.tableWidget.rowCount()
            self.gui.ui.tableWidget.insertRow( currentRowCount )

            envTableElem = EnvTableElem( env.getId(), self.__printSupported( env.supported() ) )
            for col in range( 0, 2 ):
                self.gui.ui.tableWidget.setItem(currentRowCount, col, envTableElem.getColumnItem( col ) )

    def __printSupported( self, val ):
        if val:
            return "Supported"
        else:
            return "Not supported"

    #############################
    def __setupConnections( self ):
        self.gui.ui.okButton.clicked.connect( self.gui.close )