import multiprocessing
import logging
import subprocess
import os

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox

from examples.gnr.ui.configurationdialog import ConfigurationDialog
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.fileshelper import get_dir_size
from memoryhelper import resource_size_to_display, translate_resource_index, dir_size_to_display

logger = logging.getLogger(__name__)


class ConfigurationDialogCustomizer:
    def __init__(self, gui, logic):

        assert isinstance(gui, ConfigurationDialog)

        self.gui = gui
        self.logic = logic

        self.old_plugin_port = None

        self.__setup_connections()

    def load_config(self):
        config_desc = self.logic.get_config()
        self.__load_basic_config(config_desc)
        self.__load_advance_config(config_desc)
        self.__load_manager_config(config_desc)
        self.__load_resource_config()
        self.__load_payment_config(config_desc)

    def __load_basic_config(self, config_desc):
        self.gui.ui.hostAddressLineEdit.setText(u"{}".format(config_desc.seed_host))
        self.gui.ui.hostIPLineEdit.setText(u"{}".format(config_desc.seed_host_port))
        self.gui.ui.workingDirectoryLineEdit.setText(u"{}".format(config_desc.root_path))
        self.gui.ui.performanceLabel.setText(u"{}".format(config_desc.estimated_performance))
        self.gui.ui.useIp6CheckBox.setChecked(config_desc.use_ipv6)
        self.__load_num_cores(config_desc)
        self.__load_memory_config(config_desc)
        self.__load_trust_config(config_desc)

    def __load_num_cores(self, config_desc):
        max_num_cores = multiprocessing.cpu_count()
        self.gui.ui.numCoresSlider.setMaximum(max_num_cores)
        self.gui.ui.coresMaxLabel.setText(u"{}".format(max_num_cores))

        try:
            num_cores = int(config_desc.num_cores)
        except Exception, e:
            num_cores = 1
            logger.error("Wrong value for number of cores: {}".format(str(e)))
        self.gui.ui.numCoresSlider.setValue(num_cores)

    def __load_memory_config(self, config_desc):
        mem_tab = ["kB", "MB", "GB"]
        self.gui.ui.maxResourceSizeComboBox.addItems(mem_tab)
        self.gui.ui.maxMemoryUsageComboBox.addItems(mem_tab)
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

        max_resource_size, index = resource_size_to_display(max_resource_size)
        self.gui.ui.maxResourceSizeComboBox.setCurrentIndex(index)
        self.gui.ui.maxResourceSizeSpinBox.setValue(max_resource_size)

        max_memory_size, index = resource_size_to_display(max_memory_size)
        self.gui.ui.maxMemoryUsageComboBox.setCurrentIndex(index)
        self.gui.ui.maxMemoryUsageSpinBox.setValue(max_memory_size)

    def __load_trust_config(self, config_desc):
        self.__load_trust(config_desc.computing_trust, self.gui.ui.computingTrustLineEdit,
                          self.gui.ui.computingTrustSlider)
        self.__load_trust(config_desc.requesting_trust, self.gui.ui.requestingTrustLineEdit,
                          self.gui.ui.requestingTrustSlider)

    def __load_trust(self, value, line_edit, slider):
        try:
            trust = max(min(int(round(value * 100)), 100), -100)
        except TypeError:
            logger.error("Wrong configuration trust value {}").format(value)
            trust = -100
        line_edit.setText("{}".format(trust))
        slider.setValue(trust)

    def __load_advance_config(self, config_desc):
        self.gui.ui.optimalPeerNumLineEdit.setText(u"{}".format(config_desc.opt_num_peers))

        self.__load_checkbox_param(config_desc.use_distributed_resource_management,
                                   self.gui.ui.useDistributedResCheckBox, 'use distributed res')
        self.gui.ui.distributedResNumLineEdit.setText(u"{}".format(config_desc.dist_res_num))

        self.__load_checkbox_param(config_desc.use_waiting_for_task_timeout,
                                   self.gui.ui.useWaitingForTaskTimeoutCheckBox, 'waiting for task timeout')
        self.gui.ui.waitingForTaskTimeoutLineEdit.setText(u"{}".format(config_desc.waiting_for_task_timeout))

        self.__load_checkbox_param(config_desc.send_pings, self.gui.ui.sendPingsCheckBox, 'send pings''')
        self.gui.ui.sendPingsLineEdit.setText(u"{}".format(config_desc.pings_interval))

        self.gui.ui.gettingPeersLineEdit.setText(u"{}".format(config_desc.getting_peers_interval))
        self.gui.ui.gettingTasksIntervalLineEdit.setText(u"{}".format(config_desc.getting_tasks_interval))
        self.gui.ui.nodeSnapshotIntervalLineEdit.setText(u"{}".format(config_desc.node_snapshot_interval))
        self.gui.ui.maxSendingDelayLineEdit.setText(u"{}".format(config_desc.max_results_sending_delay))

        self.gui.ui.p2pSessionTimeoutLineEdit.setText(u"{}".format(config_desc.p2p_session_timeout))
        self.gui.ui.taskSessionTimeoutLineEdit.setText(u"{}".format(config_desc.task_session_timeout))
        self.gui.ui.resourceSessionTimeoutLineEdit.setText(u"{}".format(config_desc.resource_session_timeout))

        self.gui.ui.pluginPortLineEdit.setText(u"{}".format(config_desc.plugin_port))
        self.old_plugin_port = u"{}".format(config_desc.plugin_port)

    def __load_checkbox_param(self, param, check_box, param_name=''):
        try:
            param = int(param)
            if param == 0:
                checked = False
            else:
                checked = True
        except ValueError:
            checked = True
            logger.error("Wrong configuration parameter {}: {}".format(param_name, param))
        check_box.setChecked(checked)

    def __load_manager_config(self, config_desc):
        self.gui.ui.managerAddressLineEdit.setText(u"{}".format(config_desc.manager_address))
        self.gui.ui.managerPortLineEdit.setText(u"{}".format(config_desc.manager_port))

    def __load_payment_config(self, config_desc):
        self.gui.ui.ethAccountLineEdit.setText(u"{}".format(config_desc.eth_account))

    def __load_resource_config(self):
        res_dirs = self.logic.get_res_dirs()
        self.gui.ui.computingResSize.setText(self.du(res_dirs['computing']))
        self.gui.ui.distributedResSize.setText(self.du(res_dirs['distributed']))
        self.gui.ui.receivedResSize.setText(self.du(res_dirs['received']))

    def du(self, path):
        try:
            return subprocess.check_output(['du', '-sh', path]).split()[0]
        except:
            try:
                size = get_dir_size(path)
                human_readable_size, idx = dir_size_to_display(size)
                return "{} {}".format(human_readable_size, translate_resource_index(idx))
            except Exception as err:
                logger.error(str(err))
                return "Error"

    def __setup_connections(self):
        self.gui.ui.recountButton.clicked.connect(self.__recount_performance)
        self.gui.ui.buttonBox.accepted.connect(self.__change_config)

        QtCore.QObject.connect(self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged(const int)"),
                               self.__recount_performance)

        self.gui.ui.removeComputingButton.clicked.connect(self.__remove_from_computing)
        self.gui.ui.removeDistributedButton.clicked.connect(self.__remove_from_distributed)
        self.gui.ui.removeReceivedButton.clicked.connect(self.__remove_from_received)

        QtCore.QObject.connect(self.gui.ui.requestingTrustSlider, QtCore.SIGNAL("valueChanged(const int)"),
                               self.__requesting_trust_slider_changed)
        QtCore.QObject.connect(self.gui.ui.computingTrustSlider, QtCore.SIGNAL("valueChanged(const int)"),
                               self.__computing_trust_slider_changed)
        QtCore.QObject.connect(self.gui.ui.requestingTrustLineEdit, QtCore.SIGNAL("textEdited(const QString & text)"),
                               self.__requesting_trust_edited)
        QtCore.QObject.connect(self.gui.ui.computingTrustLineEdit, QtCore.SIGNAL("textEdited(const QString & text)"),
                               self.__computing_trust_edited)

    def __remove_from_computing(self):
        reply = QMessageBox.question(self.gui.window, 'Golem Message',
                                     "Are you sure you want to remove all computed files?",
                                     QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.remove_computed_files()
            self.__load_resource_config()
        else:
            pass

    def __remove_from_distributed(self):
        reply = QMessageBox.question(self.gui.window, 'Golem Message',
                                     "Are you sure you want to remove all distributed resources?",
                                     QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.remove_distributed_files()
            self.__load_resource_config()
        else:
            pass

    def __remove_from_received(self):
        reply = QMessageBox.question(self.gui.window, 'Golem Message',
                                     "Are you sure you want to remove all received task results?",
                                     QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logic.remove_received_files()
            self.__load_resource_config()
        else:
            pass

    def __count_resource_size(self, size, index):
        if index == 1:
            size *= 1024
        if index == 2:
            size *= 1024 * 1024
        return size

    def __computing_trust_slider_changed(self):
        self.gui.ui.computingTrustLineEdit.setText("{}".format(self.gui.ui.computingTrustSlider.value()))

    def __requesting_trust_slider_changed(self):
        self.gui.ui.requestingTrustLineEdit.setText("{}".format(self.gui.ui.requestingTrustSlider.value()))

    def __computing_trust_edited(self):
        try:
            trust = int(self.gui.ui.computingTrustLineEdit.text())
            self.gui.ui.computingTrustSlider.setValue(trust)
        except ValueError:
            return

    def __requesting_trust_edited(self):
        try:
            trust = int(self.gui.ui.requestingTrustLineEdit.text())
            self.gui.ui.requestingTrustSlider.setValue(trust)
        except ValueError:
            return

    def __change_config(self):
        cfg_desc = ClientConfigDescriptor()
        self.__read_basic_config(cfg_desc)
        self.__read_advance_config(cfg_desc)
        self.__read_manager_config(cfg_desc)
        self.__read_payment_config(cfg_desc)
        self.logic.change_config(cfg_desc)

    def __read_basic_config(self, cfg_desc):
        cfg_desc.seed_host = u"{}".format(self.gui.ui.hostAddressLineEdit.text())
        try:
            cfg_desc.seed_host_port = int(self.gui.ui.hostIPLineEdit.text())
        except ValueError:
            cfg_desc.seed_host_port = u"{}".format(self.gui.ui.hostIPLineEdit.text())
        cfg_desc.root_path = u"{}".format(self.gui.ui.workingDirectoryLineEdit.text())

        cfg_desc.num_cores = u"{}".format(self.gui.ui.numCoresSlider.value())
        cfg_desc.estimated_performance = u"{}".format(self.gui.ui.performanceLabel.text())
        max_resource_size = int(self.gui.ui.maxResourceSizeSpinBox.value())
        index = self.gui.ui.maxResourceSizeComboBox.currentIndex()
        cfg_desc.max_resource_size = u"{}".format(self.__count_resource_size(max_resource_size, index))
        max_memory_size = int(self.gui.ui.maxMemoryUsageSpinBox.value())
        index = self.gui.ui.maxMemoryUsageComboBox.currentIndex()
        cfg_desc.max_memory_size = u"{}".format(self.__count_resource_size(max_memory_size, index))
        self.__read_trust_config(cfg_desc)
        cfg_desc.use_ipv6 = int(self.gui.ui.useIp6CheckBox.isChecked())

    def __read_advance_config(self, cfg_desc):
        cfg_desc.opt_num_peers = u"{}".format(self.gui.ui.optimalPeerNumLineEdit.text())
        cfg_desc.use_distributed_resource_management = int(self.gui.ui.useDistributedResCheckBox.isChecked())
        cfg_desc.dist_res_num = u"{}".format(self.gui.ui.distributedResNumLineEdit.text())
        cfg_desc.use_waiting_for_task_timeout = int(self.gui.ui.useWaitingForTaskTimeoutCheckBox.isChecked())
        cfg_desc.waiting_for_task_timeout = u"{}".format(self.gui.ui.waitingForTaskTimeoutLineEdit.text())
        cfg_desc.p2p_session_timeout = u"{}".format(self.gui.ui.p2pSessionTimeoutLineEdit.text())
        cfg_desc.task_session_timeout = u"{}".format(self.gui.ui.taskSessionTimeoutLineEdit.text())
        cfg_desc.resource_session_timeout = u"{}".format(self.gui.ui.resourceSessionTimeoutLineEdit.text())
        cfg_desc.send_pings = int(self.gui.ui.sendPingsCheckBox.isChecked())
        cfg_desc.pings_interval = u"{}".format(self.gui.ui.sendPingsLineEdit.text())
        cfg_desc.getting_peers_interval = u"{}".format(self.gui.ui.gettingPeersLineEdit.text())
        cfg_desc.getting_tasks_interval = u"{}".format(self.gui.ui.gettingTasksIntervalLineEdit.text())
        cfg_desc.node_snapshot_interval = u"{}".format(self.gui.ui.nodeSnapshotIntervalLineEdit.text())
        cfg_desc.max_results_sending_delay = u"{}".format(self.gui.ui.maxSendingDelayLineEdit.text())
        cfg_desc.plugin_port = u"{}".format(self.gui.ui.pluginPortLineEdit.text())

        if self.old_plugin_port != cfg_desc.plugin_port:
            self.__show_plugin_port_warning()

    def __read_manager_config(self, cfg_desc):
        cfg_desc.manager_address = u"{}".format(self.gui.ui.managerAddressLineEdit.text())
        try:
            cfg_desc.manager_port = int(self.gui.ui.managerPortLineEdit.text())
        except ValueError:
            cfg_desc.manager_port = u"{}".format(self.gui.ui.managerPortLineEdit.text())

    def __read_trust_config(self, cfg_desc):
        requesting_trust = self.__read_trust(self.gui.ui.requestingTrustLineEdit, self.gui.ui.requestingTrustSlider)
        computing_trust = self.__read_trust(self.gui.ui.computingTrustLineEdit, self.gui.ui.computingTrustSlider)
        cfg_desc.requesting_trust = self.__trust_to_config_trust(requesting_trust)
        cfg_desc.computing_trust = self.__trust_to_config_trust(computing_trust)

    def __trust_to_config_trust(self, trust):
        try:
            trust = max(min(float(trust) / 100.0, 1.0), -1.0)
        except ValueError:
            logger.error("Wrong trust value {}").format(trust)
            trust = -1
        return trust

    def __read_trust(self, line_edit, slider):
        try:
            trust = int(line_edit.text())
        except ValueError:
            logger.info("Wrong trust value {}").format(line_edit.text())
            trust = slider.value()
        return trust

    def __recount_performance(self):
        try:
            num_cores = int(self.gui.ui.numCoresSlider.value())
        except ValueError:
            num_cores = 1
        self.gui.ui.performanceLabel.setText(str(self.logic.recount_performance(num_cores)))

    def __read_payment_config(self, cfg_desc):
        cfg_desc.eth_account = u"{}".format(self.gui.ui.ethAccountLineEdit.text())

    def __show_plugin_port_warning(self):
        QMessageBox.warning(self.gui.window, 'Golem Message', "Restart application to change plugin port")
