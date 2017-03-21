import os

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from ethereum.utils import denoms
from mock import MagicMock, patch
from twisted.internet.defer import Deferred

from gui.application import Gui
from gui.controller.configurationdialogcustomizer import ConfigurationDialogCustomizer, logger
from gui.view.appmainwindow import AppMainWindow
from golem.tools.assertlogs import LogTestCase


class TestConfigurationDialogCustomizer(LogTestCase):

    def setUp(self):
        super(TestConfigurationDialogCustomizer, self).setUp()
        self.logic = MagicMock()
        self.gui = Gui(self.logic, AppMainWindow)
        self.gui.main_window.show = MagicMock()

    def tearDown(self):
        super(TestConfigurationDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_min_max_price(self):
        self.logic.get_res_dirs.return_value = {'computing': os.getcwd(),
                                                'distributed': os.getcwd(),
                                                'received': os.getcwd()}

        config_mock = MagicMock()
        config_mock.max_price = int(2.01 * denoms.ether)
        config_mock.min_price = int(2.0 * denoms.ether)

        config_deferred = Deferred()
        config_deferred.result = config_mock
        config_deferred.called = True

        res_dirs_deferred = Deferred()
        res_dirs_deferred.result = MagicMock()
        res_dirs_deferred.called = True

        self.logic.get_config.return_value = config_deferred
        self.logic.get_res_dirs.return_value = res_dirs_deferred

        customizer = ConfigurationDialogCustomizer(self.gui.main_window, self.logic)
        self.assertIsInstance(customizer, ConfigurationDialogCustomizer)
        self.assertEqual(float(customizer.gui.ui.maxPriceLineEdit.text()), 2.01)
        self.assertEqual(float(customizer.gui.ui.minPriceLineEdit.text()), 2.0)
        customizer.gui.ui.maxPriceLineEdit.setText(u"{}".format(1))
        customizer.gui.ui.minPriceLineEdit.setText(u"{}".format(0.0011))
        self.__click_ok(customizer)
        ccd = self.logic.change_config.call_args_list[0][0][0]
        self.assertEqual(ccd.min_price, int(0.0011 * denoms.ether))
        self.assertEqual(round(float(ccd.max_price) / denoms.ether), 1)
        customizer.gui.ui.maxPriceLineEdit.setText(u"ABCDEF")
        with self.assertLogs(logger, level=1):
            self.__click_ok(customizer)
        customizer.gui.ui.maxPriceLineEdit.setText(u"{}".format(0.3))
        customizer.gui.ui.minPriceLineEdit.setText(u"0.1 ETH")
        with self.assertLogs(logger, level=1):
            self.__click_ok(customizer)

    @patch('gui.controller.configurationdialogcustomizer.QMessageBox')
    def test_remove_from_computing(self, msg_box):
        msg_box.return_value = msg_box
        msg_box.Yes = 1
        msg_box.No = 2

        customizer = ConfigurationDialogCustomizer(self.gui.main_window, self.logic)

        msg_box.exec_.return_value = msg_box.No

        customizer._ConfigurationDialogCustomizer__remove_from_computing()
        assert not self.logic.remove_computed_files.called

        msg_box.exec_.return_value = msg_box.Yes

        customizer._ConfigurationDialogCustomizer__remove_from_computing()
        assert self.logic.remove_computed_files.called

    @patch('gui.controller.configurationdialogcustomizer.QMessageBox')
    def test_remove_from_distributed(self, msg_box):
        msg_box.return_value = msg_box
        msg_box.Yes = 1
        msg_box.No = 2

        customizer = ConfigurationDialogCustomizer(self.gui.main_window, self.logic)

        msg_box.exec_.return_value = msg_box.No

        customizer._ConfigurationDialogCustomizer__remove_from_distributed()
        assert not self.logic.remove_distributed_files.called

        msg_box.exec_.return_value = msg_box.Yes

        customizer._ConfigurationDialogCustomizer__remove_from_distributed()
        assert self.logic.remove_distributed_files.called

    @patch('gui.controller.configurationdialogcustomizer.QMessageBox')
    def test_remove_from_received(self, msg_box):
        msg_box.return_value = msg_box
        msg_box.Yes = 1
        msg_box.No = 2

        customizer = ConfigurationDialogCustomizer(self.gui.main_window, self.logic)

        msg_box.exec_.return_value = msg_box.No

        customizer._ConfigurationDialogCustomizer__remove_from_received()
        assert not self.logic.remove_received_files.called

        msg_box.exec_.return_value = msg_box.Yes

        customizer._ConfigurationDialogCustomizer__remove_from_received()
        assert self.logic.remove_received_files.called

    def __click_ok(self, customizer):
        QTest.mouseClick(customizer.gui.ui.settingsOkButton, Qt.LeftButton)
