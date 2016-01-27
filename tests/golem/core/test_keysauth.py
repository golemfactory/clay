import unittest
import tempfile
from golem.core.keysauth import KeysAuth


class KeysAuthTest(unittest.TestCase):
    def tearDown(self):
        if hasattr(KeysAuth, '_keys_dir'):
            del KeysAuth._keys_dir

    def test_keys_dir_default(self):
        km = KeysAuth()
        d1 = km.get_keys_dir()
        d2 = km.get_keys_dir()
        self.assertEqual(d1, d2)

    def test_keys_dir_default2(self):
        self.assertEqual(KeysAuth().get_keys_dir(), KeysAuth().get_keys_dir())

    def test_keys_dir_setter(self):
        km = KeysAuth()
        d = "/tmp/keys"
        km.set_keys_dir(d)
        self.assertEqual(d, km.get_keys_dir())

    def test_keys_dir_file(self):
        file = tempfile.NamedTemporaryFile()
        with self.assertRaises(AssertionError):
            km = KeysAuth()
            km.set_keys_dir(file.name)
