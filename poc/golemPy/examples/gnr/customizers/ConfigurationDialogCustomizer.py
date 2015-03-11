import multiprocessing
import logging
import subprocess

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox

from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from golem.ClientConfigDescriptor import ClientConfigDescriptor
from MemoryHelper import resourceSizeToDisplay

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
        self.__loadBasicConfig( configDesc )
        self.__loadAdvanceConfig( configDesc )
        self.__loadManagerConfig( configDesc )
        self.__loadResourceConfig()

    #############################
    def __loadBasicConfig( self, configDesc ):
        self.gui.ui.hostAddressLineEdit.setText( u"{}".format( configDesc.seedHost ) )
        self.gui.ui.hostIPLineEdit.setText( u"{}".format( configDesc.seedHostPort ) )
        self.gui.ui.workingDirectoryLineEdit.setText( u"{}".format( configDesc.rootPath ) )
        self.gui.ui.performanceLabel.setText( u"{}".format( configDesc.estimatedPerformance ) )
        self.__loadNumCores( configDesc )
        self.__loadMemoryConfig( configDesc )

    #############################
    def __loadNumCores( self, configDesc ):
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
    def __loadMemoryConfig ( self, configDesc ):
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

        maxResourceSize, index = resourceSizeToDisplay( maxResourceSize )
        self.gui.ui.maxResourceSizeComboBox.setCurrentIndex( index )
        self.gui.ui.maxResourceSizeSpinBox.setValue( maxResourceSize )

        maxMemorySize, index = resourceSizeToDisplay( maxMemorySize )
        self.gui.ui.maxMemoryUsageComboBox.setCurrentIndex( index )
        self.gui.ui.maxMemoryUsageSpinBox.setValue( maxMemorySize )

    #############################
    def __loadAdvanceConfig( self, configDesc ):
        self.gui.ui.optimalPeerNumLineEdit.setText( u"{}".format( configDesc.optNumPeers ) )

        self.__loadCheckBoxParam( configDesc.useDistributedResourceManagement, self.gui.ui.useDistributedResCheckBox, 'use distributed res' )
        self.gui.ui.distributedResNumLineEdit.setText( u"{}".format( configDesc.distResNum ) )

        self.__loadCheckBoxParam( configDesc.useWaitingForTaskTimeout, self.gui.ui.useWaitingForTaskTimeoutCheckBox, 'waiting for task timeout' )
        self.gui.ui.waitingForTaskTimeoutLineEdit.setText( u"{}".format( configDesc.waitingForTaskTimeout ) )

        self.__loadCheckBoxParam( configDesc.sendPings, self.gui.ui.sendPingsCheckBox, 'send pings''')
        self.gui.ui.sendPingsLineEdit.setText( u"{}".format( configDesc.pingsInterval ) )

        self.gui.ui.gettingPeersLineEdit.setText( u"{}".format( configDesc.gettingPeersInterval ) )
        self.gui.ui.gettingTasksIntervalLineEdit.setText( u"{}".format( configDesc.gettingTasksInterval ) )
        self.gui.ui.nodeSnapshotIntervalLineEdit.setText( u"{}".format( configDesc.nodeSnapshotInterval ) )
        self.gui.ui.maxSendingDelayLineEdit.setText( u"{}".format( configDesc.maxResultsSendingDelay ) )

    #############################
    def __loadCheckBoxParam( self, param, checkBox, paramName = '' ):
        try:
            param = int ( param )
            if param == 0:
                checked = False
            else:
                checked = True
        except ValueError:
            checked = True
            logger.error("Wrong configuration parameter {}: {}".format( paramName, param ) )
        checkBox.setChecked( checked )


    #############################
    def __loadManagerConfig( self, configDesc ):
        self.gui.ui.managerAddressLineEdit.setText( u"{}".format( configDesc.managerAddress ) )
        self.gui.ui.managerPortLineEdit.setText( u"{}".format( configDesc.managerPort ) )

    #############################
    def __loadResourceConfig( self ):
        resDirs = self.logic.getResDirs()
        self.gui.ui.computingResSize.setText( self.du( resDirs['computing'] ) )
        self.gui.ui.distributedResSize.setText( self.du(resDirs['distributed'] ))
        self.gui.ui.receivedResSize.setText( self.du( resDirs['received'] ))

    #############################
    def du( self, path ):
        try:
            return subprocess.check_output(['du', '-sh', path]).split()[0]
        except:
            return "Error"

    #############################
    def __setupConnections( self ):
        self.gui.ui.recountButton.clicked.connect( self.__recountPerformance )
        self.gui.ui.buttonBox.accepted.connect ( self.__changeConfig )

        QtCore.QObject.connect( self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged( const int )"), self.__recountPerformance )

        self.gui.ui.removeComputingButton.clicked.connect( self.__removeFromComputing )
        self.gui.ui.removeDistributedButton.clicked.connect( self.__removeFromDistributed )
        self.gui.ui.removeReceivedButton.clicked.connect( self.__removeFromReceived )

    #############################
    def __removeFromComputing( self ):
        reply = QMessageBox.question( self.gui.window, 'Golem Message', "Are you sure you want to remove all computed files?", QMessageBox.Yes | QMessageBox.No, defaultButton = QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.removeComputedFiles()
            self.__loadResourceConfig()
        else:
            pass

    #############################
    def __removeFromDistributed( self ):
        reply = QMessageBox.question( self.gui.window, 'Golem Message', "Are you sure you want to remove all distributed resources?", QMessageBox.Yes | QMessageBox.No, defaultButton = QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.removeDistributedFiles()
            self.__loadResourceConfig()
        else:
            pass

    #############################
    def __removeFromReceived( self ):
        reply = QMessageBox.question( self.gui.window, 'Golem Message', "Are you sure you want to remove all received task results?", QMessageBox.Yes | QMessageBox.No, defaultButton = QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.removeReceivedFiles()
            self.__loadResourceConfig()
        else:
            pass

    #############################
    def __countResourceSize( self, size, index ):
        if index == 1:
            size *= 1024
        if index == 2:
            size *= 1024 * 1024
        return size

    #############################
    def __changeConfig ( self ):
        cfgDesc = ClientConfigDescriptor()
        self.__readBasicConfig( cfgDesc )
        self.__readAdvanceConfig( cfgDesc )
        self.__readManagerConfig( cfgDesc )
        self.logic.changeConfig ( cfgDesc )

    def __readBasicConfig( self, cfgDesc ):
        cfgDesc.seedHost =  u"{}".format( self.gui.ui.hostAddressLineEdit.text() )
        try:
            cfgDesc.seedHostPort = int( self.gui.ui.hostIPLineEdit.text() )
        except ValueError:
            cfgDesc.seedHostPort    =  u"{}".format ( self.gui.ui.hostIPLineEdit.text() )
        cfgDesc.rootPath = u"{}".format( self.gui.ui.workingDirectoryLineEdit.text() )

        cfgDesc.numCores = u"{}".format( self.gui.ui.numCoresSlider.value() )
        cfgDesc.estimatedPerformance = u"{}".format( self.gui.ui.performanceLabel.text() )
        maxResourceSize = int( self.gui.ui.maxResourceSizeSpinBox.value() )
        index = self.gui.ui.maxResourceSizeComboBox.currentIndex()
        cfgDesc.maxResourceSize = u"{}".format( self.__countResourceSize( maxResourceSize, index ) )
        maxMemorySize = int( self.gui.ui.maxMemoryUsageSpinBox.value() )
        index = self.gui.ui.maxMemoryUsageComboBox.currentIndex()
        cfgDesc.maxMemorySize = u"{}".format( self.__countResourceSize( maxMemorySize, index ) )

    def __readAdvanceConfig( self, cfgDesc ):
        cfgDesc.optNumPeers = u"{}".format( self.gui.ui.optimalPeerNumLineEdit.text() )
        cfgDesc.useDistributedResourceManagement = int( self.gui.ui.useDistributedResCheckBox.isChecked() )
        cfgDesc.distResNum = u"{}".format( self.gui.ui.distributedResNumLineEdit.text() )
        cfgDesc.useWaitingForTaskTimeout = int( self.gui.ui.useWaitingForTaskTimeoutCheckBox.isChecked() )
        cfgDesc.waitingForTaskTimeout = u"{}".format( self.gui.ui.waitingForTaskTimeoutLineEdit.text() )
        cfgDesc.sendPings = int( self.gui.ui.sendPingsCheckBox.isChecked() )
        cfgDesc.pingsInterval = u"{}".format( self.gui.ui.sendPingsLineEdit.text() )
        cfgDesc.gettingPeersInterval = u"{}".format( self.gui.ui.gettingPeersLineEdit.text() )
        cfgDesc.gettingTasksInterval = u"{}".format( self.gui.ui.gettingTasksIntervalLineEdit.text() )
        cfgDesc.nodeSnapshotInterval = u"{}".format( self.gui.ui.nodeSnapshotIntervalLineEdit.text() )
        cfgDesc.maxResultsSendingDelay = u"{}".format( self.gui.ui.maxSendingDelayLineEdit.text() )

    def __readManagerConfig( self, cfgDesc ):
        cfgDesc.managerAddress = u"{}".format( self.gui.ui.managerAddressLineEdit.text() )
        try:
            cfgDesc.managerPort = int( self.gui.ui.managerPortLineEdit.text() )
        except ValueError:
            cfgDesc.managerPort = u"{}".format( self.gui.ui.managerPortLineEdit.text() )


    #############################
    def __recountPerformance( self ):
        try:
            numCores = int( self.gui.ui.numCoresSlider.value() )
        except:
            numCores = 1
        self.gui.ui.performanceLabel.setText( str( self.logic.recountPerformance( numCores ) ) )

