import tempfile
from random import random

from golem.core.keysauth import KeysAuth, EllipticalKeysAuth
from golem.tools.testwithappconfig import TestWithKeysAuth

class KeysAuthTest(TestWithKeysAuth):

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


class TestEllipticalKeysAuth(TestWithKeysAuth):
    def test_init(self):
        EllipticalKeysAuth.set_keys_dir(self.path)
        for i in range(100):
            ek = EllipticalKeysAuth(random())
            self.assertEqual(len(ek._private_key), 32)
            self.assertEqual(len(ek.public_key), 64)
            self.assertEqual(len(ek.key_id), 128)

    def test_sign_verify(self):
        EllipticalKeysAuth.set_keys_dir(self.path)
        ek = EllipticalKeysAuth(random())
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 100
        signature = ek.sign(data)
        self.assertTrue(ek.verify(signature, data))
        self.assertTrue(ek.verify(signature, data, ek.key_id))
        ek2 = EllipticalKeysAuth(random())
        self.assertTrue(ek2.verify(signature, data, ek.key_id))
        data2 = "23103"
        sig = ek2.sign(data2)
        self.assertTrue(ek.verify(sig, data2, ek2.key_id))

    def test_encrypt_decrypt(self):
        EllipticalKeysAuth.set_keys_dir(self.path)
        ek = EllipticalKeysAuth(random())
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 1000
        enc = ek.encrypt(data)
        self.assertEqual(ek.decrypt(enc), data)
        ek2 = EllipticalKeysAuth(random())
        self.assertEqual(ek2.decrypt(ek.encrypt(data, ek2.key_id)), data)
        data2 = "23103"
        self.assertEqual(ek.decrypt(ek2.encrypt(data2, ek.key_id)), data2)

