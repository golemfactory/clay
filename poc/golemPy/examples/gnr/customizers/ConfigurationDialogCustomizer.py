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

        memTab = ["kB","MB", "GB"]
        self.gui.ui.maxResourceSizeComboBox.addItems(memTab)
        self.gui.ui.maxMemoryUsageComboBox.addItems(memTab)
        try:
            maxResourceSize = long( configDesc.maxResourceSize )
        except Exception, e:
            maxResourceSize = 250 * 1024
            logger.error( "Wrong value for maximum resource size: {}".format( str( e ) ) )

        try:
            maxMemorySize = long( configDesc.maxMemorySize )
        except Exception, e:
            maxMemorySize = 250 * 1024
            logger.error( "Wrong value for maximum memory usage: {}".format( str( e ) ) )

        maxResourceSize, index = self.__resourceSizeToDisplay( maxResourceSize )
        self.gui.ui.maxResourceSizeComboBox.setCurrentIndex( index )
        self.gui.ui.maxResourceSizeSpinBox.setValue( maxResourceSize )

        maxMemorySize, index = self.__resourceSizeToDisplay( maxMemorySize )
        self.gui.ui.maxMemoryUsageComboBox.setCurrentIndex( index )
        self.gui.ui.maxMemoryUsageSpinBox.setValue( maxMemorySize )


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
    def __countResourceSize( self, size, index ):
        if index == 1:
            size *= 1024
        if index == 2:
            size *= 1024 * 1024
        return size

    #############################
    def __changeConfig ( self ):
        hostAddress =  u"{}".format( self.gui.ui.hostAddressLineEdit.text() )
        hostPort    =  u"{}".format ( self.gui.ui.hostIPLineEdit.text() )
        workingDirectory = u"{}".format( self.gui.ui.workingDirectoryLineEdit.text() )
        managerPort = u"{}".format( self.gui.ui.managerPortLineEdit.text() )
        numCores = u"{}".format( self.gui.ui.numCoresSlider.value() )
        estimatedPerformance = u"{}".format( self.gui.ui.performanceLabel.text() )
        maxResourceSize = int( self.gui.ui.maxResourceSizeSpinBox.value() )
        index = self.gui.ui.maxResourceSizeComboBox.currentIndex()
        maxResourceSize = u"{}".format( self.__countResourceSize( maxResourceSize, index ) )
        maxMemorySize = int( self.gui.ui.maxMemoryUsageSpinBox.value() )
        index = self.gui.ui.maxMemoryUsageComboBox.currentIndex()
        maxMemorySize = u"{}".format( self.__countResourceSize( maxMemorySize, index ) )
        self.logic.changeConfig (   hostAddress,
                                    hostPort,
                                    workingDirectory,
                                    managerPort,
                                    numCores,
                                    estimatedPerformance,
                                    maxResourceSize,
                                    maxMemorySize )

    #############################
    def __recountPerformance( self ):
        try:
            numCores = int( self.gui.ui.numCoresSlider.value() )
        except:
            numCores = 1
        self.gui.ui.performanceLabel.setText( str( self.logic.recountPerformance( numCores ) ) )

