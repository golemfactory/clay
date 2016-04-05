import unittest
from mock import Mock
from os import path
from golem.appconfig import AppConfig, CommonConfig, NodeConfig
from golem.core.simpleenv import SimpleEnv
from golem.core.keysauth import KeysAuth
from golem.tools.testdirfixture import TestDirFixture


class TestWithAppConfig(unittest.TestCase):
    def clear_config(self):
        # This is to prevent test methods from picking up AppConfigs
        # created by previously run test methods:
        self.new_node()
        if hasattr(CommonConfig, "_properties"):
            del CommonConfig._properties
        if hasattr(CommonConfig, "properties"):
            del CommonConfig.properties
        if hasattr(NodeConfig, "_properties"):
            del NodeConfig._properties
        if hasattr(NodeConfig, "properties"):
            del NodeConfig.properties

    def new_node(self):
        AppConfig.CONFIG_LOADED = False

    def setUp(self):
        self.clear_config()

    def tearDown(self):
        self.clear_config()


class TestWithKeysAuth(TestDirFixture):
    def setUp(self):
        super(TestWithKeysAuth, self).setUp()
        self.client = Mock()
        type(self.client).datadir = path.join(self.path, "datadir")

    def tearDown(self):
        if hasattr(KeysAuth, '_keys_dir'):
            del KeysAuth._keys_dir

        super(TestWithKeysAuth, self).tearDown()
