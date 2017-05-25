import os
from os import path

import golem.appconfig as appconfig

from golem.core.simpleenv import SimpleEnv
from golem.appconfig import logger, AppConfig, ClientConfigDescriptor, NodeConfig
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


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

    def test_read_estimated_performance(self):
        appconfig.ESTM_FILENAME = TestNodeConfig.no_existing_name
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()

        self.assertTrue(any("Can't open" in log for log in l.output))
        self.assertEqual(res, 0)

        appconfig.ESTM_FILENAME = TestNodeConfig.wrong_name

        SimpleEnv.env_file_name(appconfig.ESTM_FILENAME)
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any("Can't open" in log for log in l.output))

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
        self.assertTrue(any("to float" in log for log in l.output))

        with open(good_file, 'w') as f:
            f.write("abc")
        with self.assertLogs(logger, level=1) as l:
            res = NodeConfig.read_estimated_performance()
        self.assertEqual(res, 0)
        self.assertTrue(any("to float" in log for log in l.output))

    def tearDown(self):
        not_file = SimpleEnv.env_file_name(TestNodeConfig.wrong_name)
        if os.path.exists(not_file):
            os.removedirs(not_file)
        good_file = SimpleEnv.env_file_name(TestNodeConfig.good_name)
        if os.path.exists(good_file):
            os.remove(good_file)
        if hasattr(NodeConfig, "_properties"):
            del NodeConfig._properties
        if hasattr(NodeConfig, "properties"):
            del NodeConfig.properties


class TestAppConfig(TestDirFixture):

    def test_load_config(self):
        dir1 = path.join(self.path, "1")
        dir2 = path.join(self.path, "2")
        cfg1 = AppConfig.load_config(dir1, "test.ini")
        with self.assertRaises(RuntimeError):
            AppConfig.load_config(dir1, "test.ini")
        cfg2 = AppConfig.load_config(dir2, "test.ini")

        assert cfg1.config_file == path.join(dir1, "test.ini")
        assert cfg2.config_file == path.join(dir2, "test.ini")

        config_desc = ClientConfigDescriptor()
        config_desc.init_from_app_config(cfg1)
        config_desc.use_distributed_resource_management = 0
        config_desc.computing_trust = 0.23
        cfg1.change_config(config_desc)

        AppConfig._AppConfig__loaded_configs = set()  # Allow reload.

        cfgC = AppConfig.load_config(dir1, "test.ini")
        assert cfg1.get_node_name() == cfgC.get_node_name()
        config_descC = ClientConfigDescriptor()
        config_descC.init_from_app_config(cfgC)
        assert config_descC.use_distributed_resource_management
        assert config_descC.computing_trust == 0.23

        with self.assertRaises(TypeError):
            cfgC.change_config(None)
