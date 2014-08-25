import os
import multiprocessing
import logging
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QMessageBox

from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog

logger = logging.getLogger(__name__)

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

        maxNumCores = multiprocessing.cpu_count()
        self.gui.ui.numCoresSlider.setMaximum(  maxNumCores )
        self.gui.ui.coresMaxLabel.setText( u"{}".format( maxNumCores ) )

        try:
            numCores = int ( configDesc.numCores )
        except Exception, e:
            numCores = 1
            logger.error( "Wrong value for number of cores: {}".format( str( e ) )  )
        self.gui.ui.numCoresSlider.setValue( numCores )

    #############################
    def __setupConnections( self ):
        self.gui.ui.recountButton.clicked.connect( self.__recountPerformance )
        self.gui.ui.buttonBox.accepted.connect ( self.__changeConfig )

        QtCore.QObject.connect( self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged( const int )"), self.__recountPerformance )


    #############################
    def __changeConfig (self ):
        hostAddress =  u"{}".format( self.gui.ui.hostAddressLineEdit.text() )
        hostPort    =  u"{}".format ( self.gui.ui.hostIPLineEdit.text() )
        workingDirectory = u"{}".format( self.gui.ui.workingDirectoryLineEdit.text() )
        managerPort = u"{}".format( self.gui.ui.managerPortLineEdit.text() )
        numCores = u"{}".format( self.gui.ui.numCoresSlider.value() )
        estimatedPerformance = u"{}".format( self.gui.ui.performanceLabel.text() )
        self.logic.changeConfig ( hostAddress, hostPort, workingDirectory, managerPort, numCores, estimatedPerformance )
        msgBox = QMessageBox()
        msgBox.setText( "Restart application to make configuration changes" )
        msgBox.exec_()

    #############################
    def __recountPerformance( self ):
        try:
            numCores = int( self.gui.ui.numCoresSlider.value() )
        except:
            numCores = 1
        self.gui.ui.performanceLabel.setText( str( self.logic.recountPerformance( numCores ) ) )

