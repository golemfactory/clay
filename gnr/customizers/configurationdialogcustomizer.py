import multiprocessing
import logging
import subprocess

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox, QPalette

from gnr.customizers.customizer import Customizer
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.fileshelper import get_dir_size
from golem.transactions.ethereum.ethereumpaymentskeeper import EthereumAddress
from gnr.renderingtaskstate import RenderingTaskState
from golem.task.taskstate import TaskStatus
from memoryhelper import resource_size_to_display, translate_resource_index, dir_size_to_display
from gnr.benchmarks.luxrender.luxbenchmark import LuxBenchmark
from gnr.benchmarks.blender.blenderbenchmark import BlenderBenchmark

logger = logging.getLogger(__name__)


class ConfigurationDialogCustomizer(Customizer):
    """ Customizer for gui with all golem configuration option that can be changed by user
    """

    SHOW_ADVANCE_BUTTON_MESSAGES = ["Show more", "Hide"]
    SHOW_DISK_USAGE_BUTTON_MESSAGES = ["Show disk usage", "Hide"]

    def __init__(self, gui, logic):
        Customizer.__init__(self, gui, logic)

    def load_data(self):
        config_desc = self.logic.get_config()
        self.__load_basic_config(config_desc)
        self.__load_advance_config(config_desc)
        self.__load_resource_config()
        self.__load_payment_config(config_desc)

    @staticmethod
    def du(path):
        """ Imitates bash "du -h <path>" command behaviour. Returns the estiamted size of this directory
        :param str path: path to directory which size should be measured
        :return str: directory size in human readeable format (eg. 1 Mb) or "-1" if an error occurs.
        """
        try:
            size = int(subprocess.check_output(['du', '-sb', path]).split()[0])
        except (OSError, subprocess.CalledProcessError):
            try:
                size = int(get_dir_size(path))
            except OSError as err:
                logger.info("Can't open dir {}: {}".format(path, str(err)))
                return "-1"
        human_readable_size, idx = dir_size_to_display(size)
        return "{} {}".format(human_readable_size, translate_resource_index(idx))

    def _setup_connections(self):
        self.gui.ui.recountButton.clicked.connect(self.__recount_performance)
        self.gui.ui.recountLuxButton.clicked.connect(self.__run_lux_benchmark_button_clicked)
        self.gui.ui.recountBlenderButton.clicked.connect(self.__run_blender_benchmark_button_clicked)
        self.gui.ui.settingsOkButton.clicked.connect(self.__change_config)
        self.gui.ui.settingsCancelButton.clicked.connect(lambda: self.load_data())

        QtCore.QObject.connect(self.gui.ui.numCoresSlider, QtCore.SIGNAL("valueChanged(const int)"),
                               self.__recount_performance)

        self.gui.ui.showDiskButton.clicked.connect(self.__show_disk_button_clicked)
        self.gui.ui.removeComputingButton.clicked.connect(self.__remove_from_computing)
        self.gui.ui.removeReceivedButton.clicked.connect(self.__remove_from_received)
        self.gui.ui.refreshComputingButton.clicked.connect(self.__refresh_disk_computed)
        self.gui.ui.refreshReceivedButton.clicked.connect(self.__refresh_disk_received)

        QtCore.QObject.connect(self.gui.ui.requestingTrustSlider, QtCore.SIGNAL("valueChanged(const int)"),
                               self.__requesting_trust_slider_changed)
        QtCore.QObject.connect(self.gui.ui.computingTrustSlider, QtCore.SIGNAL("valueChanged(const int)"),
                               self.__computing_trust_slider_changed)
        QtCore.QObject.connect(self.gui.ui.requestingTrustLineEdit, QtCore.SIGNAL("textEdited(const QString)"),
                               self.__requesting_trust_edited)
        QtCore.QObject.connect(self.gui.ui.computingTrustLineEdit, QtCore.SIGNAL("textEdited(const QString)"),
                               self.__computing_trust_edited)
        QtCore.QObject.connect(self.gui.ui.ethAccountLineEdit, QtCore.SIGNAL("textChanged(QString)"),
                               self.__check_eth_account)

        self.gui.ui.showAdvanceButton.clicked.connect(self.__show_advance_clicked)

    def __load_basic_config(self, config_desc):
        self.gui.ui.hostAddressLineEdit.setText(u"{}".format(config_desc.seed_host))
        self.gui.ui.hostIPLineEdit.setText(u"{}".format(config_desc.seed_port))
        self.gui.ui.performanceLabel.setText(u"{}".format(config_desc.estimated_performance))
        self.gui.ui.luxPerformanceLabel.setText(u"{}".format(config_desc.estimated_lux_performance))
        self.gui.ui.blenderPerformanceLabel.setText(u"{}".format(config_desc.estimated_blender_performance))
        self.gui.ui.useIp6CheckBox.setChecked(config_desc.use_ipv6)
        self.__load_num_cores(config_desc)
        self.__load_memory_config(config_desc)
        self.__load_trust_config(config_desc)
        self.__load_trading_ratio(config_desc)

    def __load_trading_ratio(self, config):
        self.gui.ui.tradingStrategySlider.setValue(config.trading_ratio)

    def __load_num_cores(self, config_desc):
        max_num_cores = multiprocessing.cpu_count()
        self.gui.ui.numCoresSlider.setMaximum(max_num_cores)
        self.gui.ui.coresMaxLabel.setText(u"{}".format(max_num_cores))

        try:
            num_cores = int(config_desc.num_cores)
        except (ValueError, AttributeError, TypeError) as err:
            num_cores = 1
            logger.error("Wrong value for number of cores: {}".format(err))
        self.gui.ui.numCoresSlider.setValue(num_cores)

    def __load_memory_config(self, config_desc):
        mem_tab = ["kB", "MB", "GB"]
        self.gui.ui.maxResourceSizeComboBox.addItems(mem_tab)
        self.gui.ui.maxMemoryUsageComboBox.addItems(mem_tab)
        try:
            max_resource_size = long(config_desc.max_resource_size)
        except (ValueError, AttributeError, TypeError) as err:
            max_resource_size = 250 * 1024
            logger.error("Wrong value for maximum resource size: {}".format(err))

        try:
            max_memory_size = long(config_desc.max_memory_size)
        except (ValueError, AttributeError, TypeError) as err:
            max_memory_size = 250 * 1024
            logger.error("Wrong value for maximum memory usage: {}".format(err))

        max_resource_size, index = resource_size_to_display(max_resource_size)
        self.gui.ui.maxResourceSizeComboBox.setCurrentIndex(index)
        self.gui.ui.maxResourceSizeSpinBox.setValue(max_resource_size)

        max_memory_size, index = resource_size_to_display(max_memory_size)
        self.gui.ui.maxMemoryUsageComboBox.setCurrentIndex(index)
        self.gui.ui.maxMemoryUsageSpinBox.setValue(max_memory_size)

    def __run_lux_benchmark_button_clicked(self):
        self.logic.run_benchmark(LuxBenchmark(), self.gui.ui.luxPerformanceLabel)

    def __run_blender_benchmark_button_clicked(self):
        self.logic.run_benchmark(BlenderBenchmark(), self.gui.ui.blenderPerformanceLabel)

    def __load_trust_config(self, config_desc):
        self.__load_trust(config_desc.computing_trust, self.gui.ui.computingTrustLineEdit,
                          self.gui.ui.computingTrustSlider)
        self.__load_trust(config_desc.requesting_trust, self.gui.ui.requestingTrustLineEdit,
                          self.gui.ui.requestingTrustSlider)

    def __load_trust(self, value, line_edit, slider):
        try:
            trust = max(min(int(round(value * 100)), 100), -100)
        except TypeError:
            logger.error("Wrong configuration trust value {}".format(value))
            trust = -100
        line_edit.setText("{}".format(trust))
        slider.setValue(trust)

    def __load_advance_config(self, config_desc):
        self.gui.ui.advanceSettingsWidget.hide()
        self.gui.ui.showAdvanceButton.setText(ConfigurationDialogCustomizer.SHOW_ADVANCE_BUTTON_MESSAGES[0])

        self.gui.ui.optimalPeerNumLineEdit.setText(u"{}".format(config_desc.opt_peer_num))
        self.__load_checkbox_param(config_desc.use_waiting_for_task_timeout,
                                   self.gui.ui.useWaitingForTaskTimeoutCheckBox, 'waiting for task timeout')
        self.gui.ui.waitingForTaskTimeoutLineEdit.setText(u"{}".format(config_desc.waiting_for_task_timeout))

        self.__load_checkbox_param(config_desc.send_pings, self.gui.ui.sendPingsCheckBox, 'send pings''')
        self.gui.ui.sendPingsLineEdit.setText(u"{}".format(config_desc.pings_interval))

        self.gui.ui.gettingPeersLineEdit.setText(u"{}".format(config_desc.getting_peers_interval))
        self.gui.ui.gettingTasksIntervalLineEdit.setText(u"{}".format(config_desc.getting_tasks_interval))
        self.gui.ui.maxSendingDelayLineEdit.setText(u"{}".format(config_desc.max_results_sending_delay))

        self.gui.ui.p2pSessionTimeoutLineEdit.setText(u"{}".format(config_desc.p2p_session_timeout))
        self.gui.ui.taskSessionTimeoutLineEdit.setText(u"{}".format(config_desc.task_session_timeout))
        self.__load_checkbox_param(not config_desc.accept_tasks, self.gui.ui.dontAcceptTasksCheckBox,
                                   "don't accept tasks")

    @staticmethod
    def __load_checkbox_param(param, check_box, param_name=''):
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

    def __load_payment_config(self, config_desc):
        self.gui.ui.ethAccountLineEdit.setText(u"{}".format(config_desc.eth_account))
        self.__check_eth_account()
        self.gui.ui.minPriceLineEdit.setText(u"{}".format(config_desc.min_price))
        self.gui.ui.maxPriceLineEdit.setText(u"{}".format(config_desc.max_price))

    def __load_resource_config(self):
        self.gui.ui.diskWidget.hide()
        self.gui.ui.showDiskButton.setText(self.SHOW_DISK_USAGE_BUTTON_MESSAGES[0])
        self.__refresh_disk_computed()
        self.__refresh_disk_received()

    def __refresh_disk_received(self):
        res_dirs = self.logic.get_res_dirs()
        self.gui.ui.receivedResSize.setText(self.du(res_dirs['received']))

    def __refresh_disk_computed(self):
        res_dirs = self.logic.get_res_dirs()
        self.gui.ui.computingResSize.setText(self.du(res_dirs['computing']))

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
        self.__read_payment_config(cfg_desc)
        self.logic.change_config(cfg_desc)

    def __read_basic_config(self, cfg_desc):
        cfg_desc.seed_host = u"{}".format(self.gui.ui.hostAddressLineEdit.text())
        try:
            cfg_desc.seed_port = int(self.gui.ui.hostIPLineEdit.text())
        except ValueError:
            cfg_desc.seed_port = u"{}".format(self.gui.ui.hostIPLineEdit.text())

        cfg_desc.num_cores = u"{}".format(self.gui.ui.numCoresSlider.value())
        cfg_desc.estimated_performance = u"{}".format(self.gui.ui.performanceLabel.text())
        cfg_desc.estimated_lux_performance = u"{}".format(self.gui.ui.luxPerformanceLabel.text())
        cfg_desc.estimated_blender_performance = u"{}".format(self.gui.ui.blenderPerformanceLabel.text())
        max_resource_size = int(self.gui.ui.maxResourceSizeSpinBox.value())
        index = self.gui.ui.maxResourceSizeComboBox.currentIndex()
        cfg_desc.max_resource_size = u"{}".format(self.__count_resource_size(max_resource_size, index))
        max_memory_size = int(self.gui.ui.maxMemoryUsageSpinBox.value())
        cfg_desc.trading_ratio = self.gui.ui.tradingStrategySlider.value()
        index = self.gui.ui.maxMemoryUsageComboBox.currentIndex()
        cfg_desc.max_memory_size = u"{}".format(self.__count_resource_size(max_memory_size, index))
        self.__read_trust_config(cfg_desc)
        cfg_desc.use_ipv6 = int(self.gui.ui.useIp6CheckBox.isChecked())

    def __read_advance_config(self, cfg_desc):
        cfg_desc.opt_peer_num = u"{}".format(self.gui.ui.optimalPeerNumLineEdit.text())
        cfg_desc.use_waiting_for_task_timeout = int(self.gui.ui.useWaitingForTaskTimeoutCheckBox.isChecked())
        cfg_desc.waiting_for_task_timeout = u"{}".format(self.gui.ui.waitingForTaskTimeoutLineEdit.text())
        cfg_desc.p2p_session_timeout = u"{}".format(self.gui.ui.p2pSessionTimeoutLineEdit.text())
        cfg_desc.task_session_timeout = u"{}".format(self.gui.ui.taskSessionTimeoutLineEdit.text())
        cfg_desc.send_pings = int(self.gui.ui.sendPingsCheckBox.isChecked())
        cfg_desc.pings_interval = u"{}".format(self.gui.ui.sendPingsLineEdit.text())
        cfg_desc.getting_peers_interval = u"{}".format(self.gui.ui.gettingPeersLineEdit.text())
        cfg_desc.getting_tasks_interval = u"{}".format(self.gui.ui.gettingTasksIntervalLineEdit.text())
        cfg_desc.max_results_sending_delay = u"{}".format(self.gui.ui.maxSendingDelayLineEdit.text())
        cfg_desc.accept_tasks = int(not self.gui.ui.dontAcceptTasksCheckBox.isChecked())

    def __read_trust_config(self, cfg_desc):
        requesting_trust = self.__read_trust(self.gui.ui.requestingTrustLineEdit, self.gui.ui.requestingTrustSlider)
        computing_trust = self.__read_trust(self.gui.ui.computingTrustLineEdit, self.gui.ui.computingTrustSlider)
        cfg_desc.requesting_trust = self.__trust_to_config_trust(requesting_trust)
        cfg_desc.computing_trust = self.__trust_to_config_trust(computing_trust)

    def __trust_to_config_trust(self, trust):
        try:
            trust = max(min(float(trust) / 100.0, 1.0), -1.0)
        except ValueError:
            logger.error("Wrong trust value {}".format(trust))
            trust = -1
        return trust

    def __read_trust(self, line_edit, slider):
        try:
            trust = int(line_edit.text())
        except ValueError:
            logger.info("Wrong trust value {}".format(line_edit.text()))
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
        try:
            cfg_desc.min_price = int(self.gui.ui.minPriceLineEdit.text())
        except ValueError as err:
            logger.warning("Wrong min_payment value: {}".format(err))
        try:
            cfg_desc.max_price = int(self.gui.ui.maxPriceLineEdit.text())
        except ValueError as err:
            logger.warning("Wrong max_payment value: {}".format(err))
        self.__check_eth_account()

    def __set_account_error(self):
        palette = QPalette()
        palette.setColor(QPalette.Foreground, QtCore.Qt.red)
        self.gui.ui.accountStatusLabel.setPalette(palette)
        self.gui.ui.accountStatusLabel.setText("Wrong")

    def __set_account_ok(self):
        palette = QPalette()
        palette.setColor(QPalette.Foreground, QtCore.Qt.darkGreen)
        self.gui.ui.accountStatusLabel.setPalette(palette)
        self.gui.ui.accountStatusLabel.setText("OK")

    def __check_eth_account(self):
        text = self.gui.ui.ethAccountLineEdit.text()
        if EthereumAddress(text):
            self.__set_account_ok()
        else:
            self.__set_account_error()
            logger.warning("Wrong ethereum address: {}".format(text))

    def __show_advance_clicked(self):
        self.gui.ui.advanceSettingsWidget.setVisible(not self.gui.ui.advanceSettingsWidget.isVisible())
        self.gui.ui.showAdvanceButton.setText(
            self.SHOW_ADVANCE_BUTTON_MESSAGES[self.gui.ui.advanceSettingsWidget.isVisible()])

    def __show_disk_button_clicked(self):
        self.gui.ui.diskWidget.setVisible(not self.gui.ui.diskWidget.isVisible())
        self.gui.ui.showDiskButton.setText(
            self.SHOW_ADVANCE_BUTTON_MESSAGES[self.gui.ui.diskWidget.isVisible()])
