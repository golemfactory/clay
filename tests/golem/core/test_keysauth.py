import tempfile
from random import random

from golem.core.keysauth import KeysAuth, EllipticalKeysAuth
from golem.tools.testdirfixture import TestDirFixture


class KeysAuthTestBase(TestDirFixture):
    def tearDown(self):
        if hasattr(KeysAuth, '_keys_dir'):
            del KeysAuth._keys_dir


class KeysAuthTest(KeysAuthTestBase):

    def test_keys_dir_default(self):
        km = KeysAuth()
        d1 = km.get_keys_dir()
        d2 = km.get_keys_dir()
        self.assertEqual(d1, d2)

    def test_keys_dir_default2(self):
        self.assertEqual(KeysAuth().get_keys_dir(), KeysAuth().get_keys_dir())

    def test_keys_dir_setter(self):
        km = KeysAuth()
        d = self.path
        km.set_keys_dir(d)
        self.assertEqual(d, km.get_keys_dir())

    def test_keys_dir_file(self):
        file = tempfile.NamedTemporaryFile()
        with self.assertRaises(AssertionError):
            km = KeysAuth()
            km.set_keys_dir(file.name)


class TestEllipticalKeysAuth(KeysAuthTestBase):
    def test_init(self):
        EllipticalKeysAuth.set_keys_dir(self.path)
        for i in range(100):
            ek = EllipticalKeysAuth(random())
            self.assertEqual(len(ek._private_key), 32)
            self.assertEqual(len(ek.public_key), 64)
            self.assertEqual(len(ek.key_id), 128)
