import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog

class ConfigurationDialogCustomizer:
    #############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, ConfigurationDialog )

        self.gui    = gui
        self.logic  = logic

        self.__setupConnections()

    #############################
    def loadConfig( self ):
        configDesc = self.logic.getConfig()
        self.gui.ui.hostAddressLineEdit.setText( u"{}".format( configDesc.seedHost ) )
        self.gui.ui.hostIPLineEdit.setText( u"{}".format( configDesc.seedHostPort ) )
        self.gui.ui.workingDirectoryLineEdit.setText( u"{}".format( configDesc.rootPath ) )
        self.gui.ui.managerPortLineEdit.setText( u"{}".format( configDesc.managerPort ) )
        self.gui.ui.performanceLabel.setText( u"{}".format( configDesc.estimatedPerformance ) )


    #############################
    def __setupConnections( self ):
        pass

