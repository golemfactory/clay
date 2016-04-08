import unittest
from mock import Mock
from os import path
from golem.appconfig import AppConfig, CommonConfig, NodeConfig
from golem.core.keysauth import KeysAuth
from golem.tools.testdirfixture import TestDirFixture


class TestWithAppConfig(unittest.TestCase):
    pass


class TestWithKeysAuth(TestDirFixture):
    def setUp(self):
        super(TestWithKeysAuth, self).setUp()
        self.client = Mock()
        type(self.client).datadir = path.join(self.path, "datadir")

    def tearDown(self):
        if hasattr(KeysAuth, '_keys_dir'):
            del KeysAuth._keys_dir

        super(TestWithKeysAuth, self).tearDown()
