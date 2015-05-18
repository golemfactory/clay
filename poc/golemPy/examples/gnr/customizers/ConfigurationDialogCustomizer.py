import multiprocessing
import logging
import subprocess
import os

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox

from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from golem.ClientConfigDescriptor import ClientConfigDescriptor
from golem.core.filesHelper import getDirSize
from MemoryHelper import resourceSizeToDisplay, translateResourceIndex, dirSizeToDisplay

logger = logging.getLogger(__name__)

class ConfigurationDialogCustomizer:
    #############################
    def __init__( self, gui, logic ):

        assert isinstance( gui, ConfigurationDialog )

        self.gui    = gui
        self.logic  = logic

        self.oldPluginPort = None

        self.__setupConnections()

    #############################
    def loadConfig( self ):
        configDesc = self.logic.getConfig()
        self.__loadBasicConfig( configDesc )
        self.__loadAdvanceConfig( configDesc )
        self.__loadManagerConfig( configDesc )
        self.__loadResourceConfig()
        self.__loadPaymentConfig( configDesc )

    #############################
    def __loadBasicConfig( self, configDesc ):
        self.gui.ui.hostAddressLineEdit.setText( u"{}".format( configDesc.seedHost ) )
        self.gui.ui.hostIPLineEdit.setText( u"{}".format( configDesc.seedHostPort ) )
        self.gui.ui.workingDirectoryLineEdit.setText( u"{}".format( configDesc.rootPath ) )
        self.gui.ui.performanceLabel.setText( u"{}".format( configDesc.estimatedPerformance ) )
        self.__loadNumCores( configDesc )
        self.__loadMemoryConfig( configDesc )
        self.__loadTrustConfig( configDesc )

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
    def __loadTrustConfig( self, configDesc ):
        self.__loadTrust( configDesc.computingTrust, self.gui.ui.computingTrustLineEdit, self.gui.ui.computingTrustSlider )
        self.__loadTrust( configDesc.requestingTrust, self.gui.ui.requestingTrustLineEdit, self.gui.ui.requestingTrustSlider )

    #############################
    def __loadTrust(self, value, lineEdit, slider):
        try:
            trust = max(min( int( round( value * 100 ) ), 100), -100)
        except TypeError:
            logger.error("Wrong configuration trust value {}").format( value )
            trust = -100
        lineEdit.setText("{}".format( trust ))
        slider.setValue( trust )

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

        self.gui.ui.p2pSessionTimeoutLineEdit.setText( u"{}".format( configDesc.p2pSessionTimeout ) )
        self.gui.ui.taskSessionTimeoutLineEdit.setText( u"{}".format( configDesc.taskSessionTimeout ) )
        self.gui.ui.resourceSessionTimeoutLineEdit.setText( u"{}".format( configDesc.resourceSessionTimeout ) )

        self.gui.ui.pluginPortLineEdit.setText(u"{}".format( configDesc.pluginPort ) )
        self.oldPluginPort = u"{}".format( configDesc.pluginPort )

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
    def __loadPaymentConfig( self, configDesc ):
        self.gui.ui.ethAccountLineEdit.setText( u"{}".format( configDesc.ethAccount ) )

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
            try:
                size = getDirSize( path )
                humanReadableSize, idx = dirSizeToDisplay( size )
                return "{} {}".format( humanReadableSize, translateResourceIndex(idx))
            except Exception as err:
                logger.error(str(err))
                return "Error"



    #############################
    def __setupConnections( self ):
        self.gui.ui.recountButton.clicked.connect( self.__recountPerformance )
        self.gui.ui.buttonBox.accepted.connect ( self.__changeConfig )

        QtCore.QObject.connect( self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged( const int )"), self.__recountPerformance )

        self.gui.ui.removeComputingButton.clicked.connect( self.__removeFromComputing )
        self.gui.ui.removeDistributedButton.clicked.connect( self.__removeFromDistributed )
        self.gui.ui.removeReceivedButton.clicked.connect( self.__removeFromReceived )

        QtCore.QObject.connect( self.gui.ui.requestingTrustSlider, QtCore.SIGNAL("valueChanged( const int )"), self.__requestingTrustSliderChanged )
        QtCore.QObject.connect( self.gui.ui.computingTrustSlider, QtCore.SIGNAL("valueChanged( const int )"), self.__computingTrustSliderChanged )
        QtCore.QObject.connect( self.gui.ui.requestingTrustLineEdit, QtCore.SIGNAL("textEdited( const QString & text)"), self.__requestingTrustEdited )
        QtCore.QObject.connect( self.gui.ui.computingTrustLineEdit, QtCore.SIGNAL("textEdited( const QString & text)"), self.__computingTrustEdited )


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
    def __computingTrustSliderChanged( self ):
        self.gui.ui.computingTrustLineEdit.setText( "{}".format( self.gui.ui.computingTrustSlider.value() ) )

    #############################
    def __requestingTrustSliderChanged( self ):
        self.gui.ui.requestingTrustLineEdit.setText( "{}".format( self.gui.ui.requestingTrustSlider.value() ) )

    #############################
    def __computingTrustEdited( self ):
        try:
            trust = int( self.gui.ui.computingTrustLineEdit.text() )
            self.gui.ui.computingTrustSlider.setValue( trust )
        except ValueError:
            return

    #############################
    def __requestingTrustEdited( self ):
        try:
            trust = int( self.gui.ui.requestingTrustLineEdit.text() )
            self.gui.ui.requestingTrustSlider.setValue( trust )
        except ValueError:
            return

    #############################
    def __changeConfig ( self ):
        cfgDesc = ClientConfigDescriptor()
        self.__readBasicConfig( cfgDesc )
        self.__readAdvanceConfig( cfgDesc )
        self.__readManagerConfig( cfgDesc )
        self.__readPaymentConfig( cfgDesc )
        self.logic.changeConfig ( cfgDesc )

    #############################
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
        self.__readTrustConfig( cfgDesc )

    #############################
    def __readAdvanceConfig( self, cfgDesc ):
        cfgDesc.optNumPeers = u"{}".format( self.gui.ui.optimalPeerNumLineEdit.text() )
        cfgDesc.useDistributedResourceManagement = int( self.gui.ui.useDistributedResCheckBox.isChecked() )
        cfgDesc.distResNum = u"{}".format( self.gui.ui.distributedResNumLineEdit.text() )
        cfgDesc.useWaitingForTaskTimeout = int( self.gui.ui.useWaitingForTaskTimeoutCheckBox.isChecked() )
        cfgDesc.waitingForTaskTimeout = u"{}".format( self.gui.ui.waitingForTaskTimeoutLineEdit.text() )
        cfgDesc.p2pSessionTimeout = u"{}".format( self.gui.ui.p2pSessionTimeoutLineEdit.text())
        cfgDesc.taskSessionTimeout = u"{}".format( self.gui.ui.taskSessionTimeoutLineEdit.text())
        cfgDesc.resourceSessionTimeout = u"{}".format( self.gui.ui.resourceSessionTimeoutLineEdit.text())
        cfgDesc.sendPings = int( self.gui.ui.sendPingsCheckBox.isChecked() )
        cfgDesc.pingsInterval = u"{}".format( self.gui.ui.sendPingsLineEdit.text() )
        cfgDesc.gettingPeersInterval = u"{}".format( self.gui.ui.gettingPeersLineEdit.text() )
        cfgDesc.gettingTasksInterval = u"{}".format( self.gui.ui.gettingTasksIntervalLineEdit.text() )
        cfgDesc.nodeSnapshotInterval = u"{}".format( self.gui.ui.nodeSnapshotIntervalLineEdit.text() )
        cfgDesc.maxResultsSendingDelay = u"{}".format( self.gui.ui.maxSendingDelayLineEdit.text() )
        cfgDesc.pluginPort = u"{}".format( self.gui.ui.pluginPortLineEdit.text() )

        if self.oldPluginPort != cfgDesc.pluginPort:
            self.__showPluginPortWarning()

    #############################
    def __readManagerConfig( self, cfgDesc ):
        cfgDesc.managerAddress = u"{}".format( self.gui.ui.managerAddressLineEdit.text() )
        try:
            cfgDesc.managerPort = int( self.gui.ui.managerPortLineEdit.text() )
        except ValueError:
            cfgDesc.managerPort = u"{}".format( self.gui.ui.managerPortLineEdit.text() )

    #############################
    def __readTrustConfig(self, cfgDesc ):
        requestingTrust = self.__readTrust( self.gui.ui.requestingTrustLineEdit, self.gui.ui.requestingTrustSlider )
        computingTrust = self.__readTrust( self.gui.ui.computingTrustLineEdit, self.gui.ui.computingTrustSlider )
        cfgDesc.requestingTrust = self.__trustToConfigTrust( requestingTrust )
        cfgDesc.computingTrust = self.__trustToConfigTrust( computingTrust )

    #############################
    def __trustToConfigTrust(self, trust):
        try:
            trust = max(min( float( trust ) / 100.0, 1.0), -1.0)
        except ValueError:
            logger.error("Wrong trust value {}").format( trust )
            trust = -1
        return trust

    #############################
    def __readTrust( self, lineEdit, slider ):
        try:
            trust = int( lineEdit.text() )
        except ValueError:
            logger.info("Wrong trust value {}").format( lineEdit.text() )
            trust = slider.value()
        return trust

    #############################
    def __recountPerformance( self ):
        try:
            numCores = int( self.gui.ui.numCoresSlider.value() )
        except:
            numCores = 1
        self.gui.ui.performanceLabel.setText( str( self.logic.recountPerformance( numCores ) ) )

    #############################
    def __readPaymentConfig( self, cfgDesc ):
        cfgDesc.ethAccount = u"{}".format( self.gui.ui.ethAccountLineEdit.text())

    #############################
    def __showPluginPortWarning( self ):
        QMessageBox.warning( self.gui.window, 'Golem Message', "Restart application to change plugin port")