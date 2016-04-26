from mock import Mock
from os import path
from golem.core.keysauth import KeysAuth, EllipticalKeysAuth
from golem.tools.testdirfixture import TestDirFixture


class TestWithKeysAuth(TestDirFixture):
    def setUp(self):
        super(TestWithKeysAuth, self).setUp()
        self.client = Mock()
        type(self.client).datadir = path.join(self.path, "datadir")

    def tearDown(self):
        if hasattr(KeysAuth, '_keys_dir'):
            del KeysAuth._keys_dir
        if hasattr(EllipticalKeysAuth, '_keys_dir'):
            del EllipticalKeysAuth._keys_dir

        super(TestWithKeysAuth, self).tearDown()
