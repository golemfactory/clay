import os
import re

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest
from mock import MagicMock
from twisted.internet.defer import Deferred
from ethereum.utils import denoms

from gnr.application import GNRGui
from gnr.customizers.configurationdialogcustomizer import ConfigurationDialogCustomizer, logger
from gnr.ui.appmainwindow import AppMainWindow
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestDu(TestDirFixture):

    def test_du(self):
        files_ = self.additional_dir_content([1, [1]])
        testdir = self.path
        testdir2 = os.path.dirname(files_[1])
        testfile1 = files_[0]
        testfile2 = files_[1]
        res = ConfigurationDialogCustomizer.du("notexisting")
        self.assertEqual(res, "-1")
        res = ConfigurationDialogCustomizer.du(testdir)
        try:
            size = float(res)
        except ValueError:
            size, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreaterEqual(float(size), 0.0)
        with open(os.path.join(testdir, testfile1), 'w') as f:
            f.write("a" * 10000)
        res = ConfigurationDialogCustomizer.du(testdir)
        size1, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(float(size1), float(size))
        if not os.path.exists(testdir2):
            os.makedirs(testdir2)
        with open(os.path.join(testdir2, testfile2), 'w') as f:
            f.write("123" * 10000)
        res = ConfigurationDialogCustomizer.du(testdir)
        size2, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(float(size2), float(size1))
        res = ConfigurationDialogCustomizer.du(".")
        try:
            size = float(res)
        except ValueError:
            size, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(size, 0)


class TestConfigurationDialogCustomizer(LogTestCase):

    def setUp(self):
        super(TestConfigurationDialogCustomizer, self).setUp()
        self.logic = MagicMock()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestConfigurationDialogCustomizer, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

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

        customizer = ConfigurationDialogCustomizer(self.gnrgui.main_window, self.logic)
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

    def __click_ok(self, customizer):
        QTest.mouseClick(customizer.gui.ui.settingsOkButton, Qt.LeftButton)
