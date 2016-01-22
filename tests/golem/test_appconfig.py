import os
import shutil
import unittest

from mock import patch, MagicMock

import golem.appconfig as appconfig

from golem.core.simpleenv import SimpleEnv
from golem.appconfig import NodeConfig, logger, AppConfig, ClientConfigDescriptor
from golem.tools.assertlogs import LogTestCase


class TestNodeConfig(LogTestCase):
    no_existing_name = "NOTEXISTING"
    wrong_name = "WRONGSETTINGS"
    good_name = "GOODSETTINGS"
    config_val = "1024.56"

    def setUp(self):

        not_file = SimpleEnv.env_file_name(TestNodeConfig.wrong_name)
        if not os.path.exists(not_file):
            os.makedirs(not_file)
        good_file = SimpleEnv.env_file_name(TestNodeConfig.good_name)
        with open(good_file, 'w') as f:
            f.write(TestNodeConfig.config_val)

    def test_default_variables(self):
        self.assertTrue(os.path.isdir(appconfig.DEFAULT_ROOT_PATH))

    def test_read_estimated_performance(self):
        appconfig.ESTM_FILENAME = TestNodeConfig.no_existing_name
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()

        self.assertTrue(any(["Can't open" in log for log in l.output]))
        self.assertEqual(res, 0)

        appconfig.ESTM_FILENAME = TestNodeConfig.wrong_name

        not_file = SimpleEnv.env_file_name(appconfig.ESTM_FILENAME)
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any(["Can't open" in log for log in l.output]))

        appconfig.ESTM_FILENAME = TestNodeConfig.good_name
        good_file = SimpleEnv.env_file_name(appconfig.ESTM_FILENAME)
        res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, "1024.6")

        with open(good_file, 'w') as f:
            f.write("1000")
        res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, "1000.0")

        with open(good_file, 'w') as f:
            f.write("")
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any(["to float" in log for log in l.output]))

        with open(good_file, 'w') as f:
            f.write("abc")
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any(["to float" in log for log in l.output]))

    def tearDown(self):
        not_file = SimpleEnv.env_file_name(TestNodeConfig.wrong_name)
        if os.path.exists(not_file):
            os.removedirs(not_file)
        good_file = SimpleEnv.env_file_name(TestNodeConfig.good_name)
        if os.path.exists(good_file):
            os.remove(good_file)


class TestAppConfig(unittest.TestCase):
    def setUp(self):
        SimpleEnv.DATA_DIRECTORY = os.path.abspath("tmpdir")
        if not os.path.isdir(SimpleEnv.DATA_DIRECTORY):
            os.makedirs(SimpleEnv.DATA_DIRECTORY)

    @patch("golem.appconfig.ProcessService", autospec=True)
    def test_load_config(self, process_service_mock):
        m = MagicMock()
        m.register_self.return_value = 0
        process_service_mock.return_value = m
        node0 = AppConfig.load_config("test.ini").get_node_name()
        m.register_self.return_value = 1
        AppConfig.CONFIG_LOADED = False
        node1 = AppConfig.load_config("test.ini").get_node_name()
        self.assertNotEqual(node0, node1)
        m.register_self.return_value = 2
        AppConfig.CONFIG_LOADED = False
        node2 = AppConfig.load_config("test.ini").get_node_name()
        self.assertNotEqual(node0, node2)
        self.assertNotEqual(node1, node2)
        AppConfig.CONFIG_LOADED = False
        m.register_self.return_value = 0
        cfg = AppConfig.load_config("test.ini")
        self.assertEqual(node0, cfg.get_node_name())
        config_desc = ClientConfigDescriptor()
        config_desc.init_from_app_config(cfg)
        config_desc.use_distributed_resource_management = 0
        config_desc.computing_trust = 0.23
        cfg.change_config(config_desc, "test.ini")
        AppConfig.CONFIG_LOADED = False
        cfgC = AppConfig.load_config("test.ini")
        self.assertEqual(node0, cfgC.get_node_name())
        config_descC = ClientConfigDescriptor()
        config_descC.init_from_app_config(cfgC)
        self.assertFalse(config_descC.use_distributed_resource_management)
        self.assertEqual(config_descC.computing_trust, 0.23)
        AppConfig.CONFIG_LOADED = False
        m.register_self.return_value = 1
        cfg1 = AppConfig.load_config("test.ini")
        self.assertEqual(node1, cfg1.get_node_name())
        config_desc1 = ClientConfigDescriptor()
        config_desc1.init_from_app_config(cfg1)
        self.assertTrue(config_desc1.use_distributed_resource_management)
        self.assertEqual(config_desc1.computing_trust, appconfig.COMPUTING_TRUST)
        config_desc1.computing_trust = 0.38
        cfg1.change_config(config_desc1, "test.ini")
        AppConfig.CONFIG_LOADED = False
        cfg2 = AppConfig.load_config("test.ini")
        config_desc1.init_from_app_config(cfg2)
        self.assertEqual(config_desc1.computing_trust, 0.38)

    def tearDown(self):
        if os.path.isdir(SimpleEnv.DATA_DIRECTORY):
            shutil.rmtree(SimpleEnv.DATA_DIRECTORY)


