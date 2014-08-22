import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QMessageBox

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
         self.gui.ui.buttonBox.accepted.connect ( self.__changeConfig )

    #############################
    def __changeConfig (self ):
        hostAddress =  u"{}".format( self.gui.ui.hostAddressLineEdit.text() )
        hostPort    =  u"{}".format ( self.gui.ui.hostIPLineEdit.text() )
        workingDirectory = u"{}".format( self.gui.ui.workingDirectoryLineEdit.text() )
        managerPort = u"{}".format( self.gui.ui.managerPortLineEdit.text() )
        self.logic.changeConfig ( hostAddress, hostPort, workingDirectory, managerPort )
        msgBox = QMessageBox()
        msgBox.setText( "Restart application to make configuration changes" )
        msgBox.exec_()


