import multiprocessing
import logging
import subprocess
import os

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox

from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from golem.ClientConfigDescriptor import ClientConfigDescriptor
from golem.core.fileshelper import get_dir_size
from MemoryHelper import resource_sizeToDisplay, translateResourceIndex, dirSizeToDisplay

logger = logging.getLogger(__name__)

class ConfigurationDialogCustomizer:
    #############################
    def __init__(self, gui, logic):

        assert isinstance(gui, ConfigurationDialog)

        self.gui    = gui
        self.logic  = logic

        self.oldPluginPort = None

        self.__setup_connections()

    #############################
    def load_config(self):
        config_desc = self.logic.getConfig()
        self.__loadBasicConfig(config_desc)
        self.__loadAdvanceConfig(config_desc)
        self.__loadManagerConfig(config_desc)
        self.__loadResourceConfig()
        self.__loadPaymentConfig(config_desc)

    #############################
    def __loadBasicConfig(self, config_desc):
        self.gui.ui.hostAddressLineEdit.setText(u"{}".format(config_desc.seed_host))
        self.gui.ui.hostIPLineEdit.setText(u"{}".format(config_desc.seed_host_port))
        self.gui.ui.workingDirectoryLineEdit.setText(u"{}".format(config_desc.root_path))
        self.gui.ui.performanceLabel.setText(u"{}".format(config_desc.estimated_performance))
        self.gui.ui.useIp6CheckBox.setChecked(config_desc.use_ipv6)
        self.__loadNumCores(config_desc)
        self.__loadMemoryConfig(config_desc)
        self.__loadTrustConfig(config_desc)

    #############################
    def __loadNumCores(self, config_desc):
        maxNumCores = multiprocessing.cpu_count()
        self.gui.ui.numCoresSlider.setMaximum(maxNumCores)
        self.gui.ui.coresMaxLabel.setText(u"{}".format(maxNumCores))

        try:
            num_cores = int (config_desc.num_cores)
        except Exception, e:
            num_cores = 1
            logger.error("Wrong value for number of cores: {}".format(str(e)))
        self.gui.ui.numCoresSlider.setValue(num_cores)

    #############################
    def __loadMemoryConfig (self, config_desc):
        memTab = ["kB","MB", "GB"]
        self.gui.ui.maxResourceSizeComboBox.addItems(memTab)
        self.gui.ui.maxMemoryUsageComboBox.addItems(memTab)
        try:
            max_resource_size = long(config_desc.max_resource_size)
        except Exception, e:
            max_resource_size = 250 * 1024
            logger.error("Wrong value for maximum resource size: {}".format(str(e)))

        try:
            max_memory_size = long(config_desc.max_memory_size)
        except Exception, e:
            max_memory_size = 250 * 1024
            logger.error("Wrong value for maximum memory usage: {}".format(str(e)))

        max_resource_size, index = resource_sizeToDisplay(max_resource_size)
        self.gui.ui.maxResourceSizeComboBox.setCurrentIndex(index)
        self.gui.ui.maxResourceSizeSpinBox.setValue(max_resource_size)

        max_memory_size, index = resource_sizeToDisplay(max_memory_size)
        self.gui.ui.maxMemoryUsageComboBox.setCurrentIndex(index)
        self.gui.ui.maxMemoryUsageSpinBox.setValue(max_memory_size)

    #############################
    def __loadTrustConfig(self, config_desc):
        self.__loadTrust(config_desc.computing_trust, self.gui.ui.computingTrustLineEdit, self.gui.ui.computingTrustSlider)
        self.__loadTrust(config_desc.requesting_trust, self.gui.ui.requestingTrustLineEdit, self.gui.ui.requestingTrustSlider)

    #############################
    def __loadTrust(self, value, lineEdit, slider):
        try:
            trust = max(min(int(round(value * 100)), 100), -100)
        except TypeError:
            logger.error("Wrong configuration trust value {}").format(value)
            trust = -100
        lineEdit.setText("{}".format(trust))
        slider.setValue(trust)

    #############################
    def __loadAdvanceConfig(self, config_desc):
        self.gui.ui.optimalPeerNumLineEdit.setText(u"{}".format(config_desc.opt_num_peers))

        self.__loadCheckBoxParam(config_desc.use_distributed_resource_management, self.gui.ui.useDistributedResCheckBox, 'use distributed res')
        self.gui.ui.distributedResNumLineEdit.setText(u"{}".format(config_desc.dist_res_num))

        self.__loadCheckBoxParam(config_desc.use_waiting_for_task_timeout, self.gui.ui.useWaitingForTaskTimeoutCheckBox, 'waiting for task timeout')
        self.gui.ui.waitingForTaskTimeoutLineEdit.setText(u"{}".format(config_desc.waiting_for_task_timeout))

        self.__loadCheckBoxParam(config_desc.send_pings, self.gui.ui.sendPingsCheckBox, 'send pings''')
        self.gui.ui.sendPingsLineEdit.setText(u"{}".format(config_desc.pings_interval))

        self.gui.ui.gettingPeersLineEdit.setText(u"{}".format(config_desc.getting_peers_interval))
        self.gui.ui.gettingTasksIntervalLineEdit.setText(u"{}".format(config_desc.getting_tasks_interval))
        self.gui.ui.nodeSnapshotIntervalLineEdit.setText(u"{}".format(config_desc.node_snapshot_interval))
        self.gui.ui.maxSendingDelayLineEdit.setText(u"{}".format(config_desc.max_results_sending_delay))

        self.gui.ui.p2pSessionTimeoutLineEdit.setText(u"{}".format(config_desc.p2p_session_timeout))
        self.gui.ui.taskSessionTimeoutLineEdit.setText(u"{}".format(config_desc.task_session_timeout))
        self.gui.ui.resourceSessionTimeoutLineEdit.setText(u"{}".format(config_desc.resource_session_timeout))

        self.gui.ui.pluginPortLineEdit.setText(u"{}".format(config_desc.plugin_port))
        self.oldPluginPort = u"{}".format(config_desc.plugin_port)

    #############################
    def __loadCheckBoxParam(self, param, checkBox, paramName = ''):
        try:
            param = int (param)
            if param == 0:
                checked = False
            else:
                checked = True
        except ValueError:
            checked = True
            logger.error("Wrong configuration parameter {}: {}".format(paramName, param))
        checkBox.setChecked(checked)

    #############################
    def __loadManagerConfig(self, config_desc):
        self.gui.ui.managerAddressLineEdit.setText(u"{}".format(config_desc.manager_address))
        self.gui.ui.managerPortLineEdit.setText(u"{}".format(config_desc.manager_port))

    #############################
    def __loadPaymentConfig(self, config_desc):
        self.gui.ui.ethAccountLineEdit.setText(u"{}".format(config_desc.eth_account))

    #############################
    def __loadResourceConfig(self):
        resDirs = self.logic.get_res_dirs()
        self.gui.ui.computingResSize.setText(self.du(resDirs['computing']))
        self.gui.ui.distributedResSize.setText(self.du(resDirs['distributed']))
        self.gui.ui.receivedResSize.setText(self.du(resDirs['received']))

    #############################
    def du(self, path):
        try:
            return subprocess.check_output(['du', '-sh', path]).split()[0]
        except:
            try:
                size = get_dir_size(path)
                humanReadableSize, idx = dirSizeToDisplay(size)
                return "{} {}".format(humanReadableSize, translateResourceIndex(idx))
            except Exception as err:
                logger.error(str(err))
                return "Error"

    #############################
    def __setup_connections(self):
        self.gui.ui.recountButton.clicked.connect(self.__recountPerformance)
        self.gui.ui.buttonBox.accepted.connect (self.__change_config)

        QtCore.QObject.connect(self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged(const int)"), self.__recountPerformance)

        self.gui.ui.removeComputingButton.clicked.connect(self.__removeFromComputing)
        self.gui.ui.removeDistributedButton.clicked.connect(self.__removeFromDistributed)
        self.gui.ui.removeReceivedButton.clicked.connect(self.__removeFromReceived)

        QtCore.QObject.connect(self.gui.ui.requestingTrustSlider, QtCore.SIGNAL("valueChanged(const int)"), self.__requestingTrustSliderChanged)
        QtCore.QObject.connect(self.gui.ui.computingTrustSlider, QtCore.SIGNAL("valueChanged(const int)"), self.__computingTrustSliderChanged)
        QtCore.QObject.connect(self.gui.ui.requestingTrustLineEdit, QtCore.SIGNAL("textEdited(const QString & text)"), self.__requestingTrustEdited)
        QtCore.QObject.connect(self.gui.ui.computingTrustLineEdit, QtCore.SIGNAL("textEdited(const QString & text)"), self.__computingTrustEdited)

    #############################
    def __removeFromComputing(self):
        reply = QMessageBox.question(self.gui.window, 'Golem Message', "Are you sure you want to remove all computed files?", QMessageBox.Yes | QMessageBox.No, defaultButton = QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.remove_computed_files()
            self.__loadResourceConfig()
        else:
            pass

    #############################
    def __removeFromDistributed(self):
        reply = QMessageBox.question(self.gui.window, 'Golem Message', "Are you sure you want to remove all distributed resources?", QMessageBox.Yes | QMessageBox.No, defaultButton = QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.remove_distributed_files()
            self.__loadResourceConfig()
        else:
            pass

    #############################
    def __removeFromReceived(self):
        reply = QMessageBox.question(self.gui.window, 'Golem Message', "Are you sure you want to remove all received task results?", QMessageBox.Yes | QMessageBox.No, defaultButton = QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.remove_received_files()
            self.__loadResourceConfig()
        else:
            pass

    #############################
    def __countResourceSize(self, size, index):
        if index == 1:
            size *= 1024
        if index == 2:
            size *= 1024 * 1024
        return size

    #############################
    def __computingTrustSliderChanged(self):
        self.gui.ui.computingTrustLineEdit.setText("{}".format(self.gui.ui.computingTrustSlider.value()))

    #############################
    def __requestingTrustSliderChanged(self):
        self.gui.ui.requestingTrustLineEdit.setText("{}".format(self.gui.ui.requestingTrustSlider.value()))

    #############################
    def __computingTrustEdited(self):
        try:
            trust = int(self.gui.ui.computingTrustLineEdit.text())
            self.gui.ui.computingTrustSlider.setValue(trust)
        except ValueError:
            return

    #############################
    def __requestingTrustEdited(self):
        try:
            trust = int(self.gui.ui.requestingTrustLineEdit.text())
            self.gui.ui.requestingTrustSlider.setValue(trust)
        except ValueError:
            return

    #############################
    def __change_config (self):
        cfgDesc = ClientConfigDescriptor()
        self.__readBasicConfig(cfgDesc)
        self.__readAdvanceConfig(cfgDesc)
        self.__readManagerConfig(cfgDesc)
        self.__readPaymentConfig(cfgDesc)
        self.logic.change_config (cfgDesc)

    #############################
    def __readBasicConfig(self, cfgDesc):
        cfgDesc.seed_host = u"{}".format(self.gui.ui.hostAddressLineEdit.text())
        try:
            cfgDesc.seed_host_port = int(self.gui.ui.hostIPLineEdit.text())
        except ValueError:
            cfgDesc.seed_host_port = u"{}".format (self.gui.ui.hostIPLineEdit.text())
        cfgDesc.root_path = u"{}".format(self.gui.ui.workingDirectoryLineEdit.text())

        cfgDesc.num_cores = u"{}".format(self.gui.ui.numCoresSlider.value())
        cfgDesc.estimated_performance = u"{}".format(self.gui.ui.performanceLabel.text())
        max_resource_size = int(self.gui.ui.maxResourceSizeSpinBox.value())
        index = self.gui.ui.maxResourceSizeComboBox.currentIndex()
        cfgDesc.max_resource_size = u"{}".format(self.__countResourceSize(max_resource_size, index))
        max_memory_size = int(self.gui.ui.maxMemoryUsageSpinBox.value())
        index = self.gui.ui.maxMemoryUsageComboBox.currentIndex()
        cfgDesc.max_memory_size = u"{}".format(self.__countResourceSize(max_memory_size, index))
        self.__readTrustConfig(cfgDesc)
        cfgDesc.use_ipv6 = int(self.gui.ui.useIp6CheckBox.isChecked())

    #############################
    def __readAdvanceConfig(self, cfgDesc):
        cfgDesc.opt_num_peers = u"{}".format(self.gui.ui.optimalPeerNumLineEdit.text())
        cfgDesc.use_distributed_resource_management = int(self.gui.ui.useDistributedResCheckBox.isChecked())
        cfgDesc.dist_res_num = u"{}".format(self.gui.ui.distributedResNumLineEdit.text())
        cfgDesc.use_waiting_for_task_timeout = int(self.gui.ui.useWaitingForTaskTimeoutCheckBox.isChecked())
        cfgDesc.waiting_for_task_timeout = u"{}".format(self.gui.ui.waitingForTaskTimeoutLineEdit.text())
        cfgDesc.p2p_session_timeout = u"{}".format(self.gui.ui.p2pSessionTimeoutLineEdit.text())
        cfgDesc.task_session_timeout = u"{}".format(self.gui.ui.taskSessionTimeoutLineEdit.text())
        cfgDesc.resource_session_timeout = u"{}".format(self.gui.ui.resourceSessionTimeoutLineEdit.text())
        cfgDesc.send_pings = int(self.gui.ui.sendPingsCheckBox.isChecked())
        cfgDesc.pings_interval = u"{}".format(self.gui.ui.sendPingsLineEdit.text())
        cfgDesc.getting_peers_interval = u"{}".format(self.gui.ui.gettingPeersLineEdit.text())
        cfgDesc.getting_tasks_interval = u"{}".format(self.gui.ui.gettingTasksIntervalLineEdit.text())
        cfgDesc.node_snapshot_interval = u"{}".format(self.gui.ui.nodeSnapshotIntervalLineEdit.text())
        cfgDesc.max_results_sending_delay = u"{}".format(self.gui.ui.maxSendingDelayLineEdit.text())
        cfgDesc.plugin_port = u"{}".format(self.gui.ui.pluginPortLineEdit.text())

        if self.oldPluginPort != cfgDesc.plugin_port:
            self.__showPluginPortWarning()

    #############################
    def __readManagerConfig(self, cfgDesc):
        cfgDesc.manager_address = u"{}".format(self.gui.ui.managerAddressLineEdit.text())
        try:
            cfgDesc.manager_port = int(self.gui.ui.managerPortLineEdit.text())
        except ValueError:
            cfgDesc.manager_port = u"{}".format(self.gui.ui.managerPortLineEdit.text())

    #############################
    def __readTrustConfig(self, cfgDesc):
        requesting_trust = self.__readTrust(self.gui.ui.requestingTrustLineEdit, self.gui.ui.requestingTrustSlider)
        computing_trust = self.__readTrust(self.gui.ui.computingTrustLineEdit, self.gui.ui.computingTrustSlider)
        cfgDesc.requesting_trust = self.__trustToConfigTrust(requesting_trust)
        cfgDesc.computing_trust = self.__trustToConfigTrust(computing_trust)

    #############################
    def __trustToConfigTrust(self, trust):
        try:
            trust = max(min(float(trust) / 100.0, 1.0), -1.0)
        except ValueError:
            logger.error("Wrong trust value {}").format(trust)
            trust = -1
        return trust

    #############################
    def __readTrust(self, lineEdit, slider):
        try:
            trust = int(lineEdit.text())
        except ValueError:
            logger.info("Wrong trust value {}").format(lineEdit.text())
            trust = slider.value()
        return trust

    #############################
    def __recountPerformance(self):
        try:
            num_cores = int(self.gui.ui.numCoresSlider.value())
        except:
            num_cores = 1
        self.gui.ui.performanceLabel.setText(str(self.logic.recountPerformance(num_cores)))

    #############################
    def __readPaymentConfig(self, cfgDesc):
        cfgDesc.eth_account = u"{}".format(self.gui.ui.ethAccountLineEdit.text())

    #############################
    def __showPluginPortWarning(self):
        QMessageBox.warning(self.gui.window, 'Golem Message', "Restart application to change plugin port")