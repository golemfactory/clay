from os import path
from random import random

from golem.core.keysauth import KeysAuth, EllipticalKeysAuth, RSAKeysAuth
from golem.tools.testwithappconfig import TestWithKeysAuth


class KeysAuthTest(TestWithKeysAuth):

    def test_keys_dir_default(self):
        km = KeysAuth(self.path)
        d1 = km.get_keys_dir()
        d2 = km.get_keys_dir()
        self.assertEqual(d1, d2)

    def test_keys_dir_default2(self):
        self.assertEqual(KeysAuth(self.path).get_keys_dir(), KeysAuth(self.path).get_keys_dir())

    def test_keys_dir_default3(self):
        KeysAuth.get_keys_dir()
        assert path.isdir(KeysAuth._keys_dir)

    def test_keys_dir_setter(self):
        km = KeysAuth(self.path)
        d = path.join(self.path, "blablabla")
        km.set_keys_dir(d)
        self.assertEqual(d, km.get_keys_dir())

    def test_keys_dir_file(self):
        file_ = self.additional_dir_content([1])[0]
        with self.assertRaises(AssertionError):
            km = KeysAuth(self.path)
            km.set_keys_dir(file_)


class TestRSAKeysAuth(TestWithKeysAuth):
    # FIXME Fix this test and add encrypt decrypt
    def test_sign_verify(self):
        km = RSAKeysAuth(self.path)
    #
    #     data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 100
    #     signature = km.sign(data)
    #     assert km.verify(signature, data)
    #     assert km.verify(signature, data, km.key_id)
    #     km2 = RSAKeysAuth(self.path, "PRIVATE2", "PUBLIC2")
    #     assert km2.verify(signature, data, km.key_id)
    #     data2 = "ABBALJL\nafaoawuoauofa\ru0180141mfa\t" * 100
    #     signature2 = km2.sign(data2)
    #     assert km.verify(signature2, data2, km2.key_id)


class TestEllipticalKeysAuth(TestWithKeysAuth):
    def test_init(self):
        for i in range(100):
            ek = EllipticalKeysAuth(path.join(self.path), str(random()))
            self.assertEqual(len(ek._private_key), 32)
            self.assertEqual(len(ek.public_key), 64)
            self.assertEqual(len(ek.key_id), 128)

    def test_sign_verify(self):
        ek = EllipticalKeysAuth(self.path)
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 100
        signature = ek.sign(data)
        self.assertTrue(ek.verify(signature, data))
        self.assertTrue(ek.verify(signature, data, ek.key_id))
        ek2 = EllipticalKeysAuth(path.join(self.path, str(random())))
        self.assertTrue(ek2.verify(signature, data, ek.key_id))
        data2 = "23103"
        sig = ek2.sign(data2)
        self.assertTrue(ek.verify(sig, data2, ek2.key_id))

    def test_encrypt_decrypt(self):
        ek = EllipticalKeysAuth(path.join(self.path, str(random())))
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 1000
        enc = ek.encrypt(data)
        self.assertEqual(ek.decrypt(enc), data)
        ek2 = EllipticalKeysAuth(path.join(self.path, str(random())))
        self.assertEqual(ek2.decrypt(ek.encrypt(data, ek2.key_id)), data)
        data2 = "23103"
        self.assertEqual(ek.decrypt(ek2.encrypt(data2, ek.key_id)), data2)
