import multiprocessing
import logging
from PyQt4 import QtCore

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

        self.gui.ui.maxResourceSizeComboBox.addItems(["kB","MB", "GB"])
        try:
            maxResourceSize = long( configDesc.maxResourceSize )
        except Exception, e:
            maxResourceSize = 250 * 1024
            logger.error( "Wrong value for maximum resource size: {}".format( str( e ) ) )

        maxResourceSize, index = self.__resourceSizeToDisplay( maxResourceSize )

        self.gui.ui.maxResourceSizeComboBox.setCurrentIndex( index )
        self.gui.ui.maxResourceSizeSpinBox.setValue( maxResourceSize )


    #############################
    def __resourceSizeToDisplay( self, maxResourceSize ):
        if maxResourceSize / ( 1024 * 1024 ) > 0:
            maxResourceSize /= ( 1024 * 1024 )
            index = 2
        elif maxResourceSize / 1024 > 0:
            maxResourceSize /= 1024
            index = 1
        else:
            index = 0
        return maxResourceSize, index

    #############################
    def __setupConnections( self ):
        self.gui.ui.recountButton.clicked.connect( self.__recountPerformance )
        self.gui.ui.buttonBox.accepted.connect ( self.__changeConfig )

        QtCore.QObject.connect( self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged( const int )"), self.__recountPerformance )

    #############################
    def __countMaxResourceSize( self ):
        maxResourceSize = int( self.gui.ui.maxResourceSizeSpinBox.value() )
        index = self.gui.ui.maxResourceSizeComboBox.currentIndex()
        if index == 1:
            maxResourceSize *= 1024
        if index == 2:
            maxResourceSize *= 1024 * 1024
        return maxResourceSize

    #############################
    def __changeConfig ( self ):
        hostAddress =  u"{}".format( self.gui.ui.hostAddressLineEdit.text() )
        hostPort    =  u"{}".format ( self.gui.ui.hostIPLineEdit.text() )
        workingDirectory = u"{}".format( self.gui.ui.workingDirectoryLineEdit.text() )
        managerPort = u"{}".format( self.gui.ui.managerPortLineEdit.text() )
        numCores = u"{}".format( self.gui.ui.numCoresSlider.value() )
        estimatedPerformance = u"{}".format( self.gui.ui.performanceLabel.text() )
        maxResourceSize = u"{}".format( self.__countMaxResourceSize() )
        self.logic.changeConfig (   hostAddress,
                                    hostPort,
                                    workingDirectory,
                                    managerPort,
                                    numCores,
                                    estimatedPerformance,
                                    maxResourceSize )

    #############################
    def __recountPerformance( self ):
        try:
            numCores = int( self.gui.ui.numCoresSlider.value() )
        except:
            numCores = 1
        self.gui.ui.performanceLabel.setText( str( self.logic.recountPerformance( numCores ) ) )

