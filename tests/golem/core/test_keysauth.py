import time
from os import path
from random import random, randint

from devp2p.crypto import ECCx

from golem.core.keysauth import KeysAuth, EllipticalKeysAuth, RSAKeysAuth, get_random, get_random_float, sha2, sha3
from golem.core.simpleserializer import CBORSerializer
from golem.network.transport.message import MessageWantToComputeTask
from golem.tools.testwithappconfig import TestWithKeysAuth


class KeysAuthTest(TestWithKeysAuth):

    def test_sha(self):
        """ Test sha2 and sha3 methods """
        test_str = "qaz123WSX"
        expected_sha2 = int("0x47b151cede6e6a05140af0da56cb889c40adaf4fddd9f17435cdeb5381be0a62", 16)
        expected_sha3 = "dcb31d2846f6d2bd2a2b0a6690ac59714c6a47c625c362886123e7f99b6ee3ea"
        self.assertEqual(sha2(test_str), expected_sha2)
        self.assertEqual(sha3(test_str).encode('hex'), expected_sha3)

    def test_keys_dir_default(self):
        km = KeysAuth(self.path)
        d1 = km.get_keys_dir()
        d2 = km.get_keys_dir()
        self.assertEqual(d1, d2)

    def test_get_difficulty(self):
        """ Test get_difficulty method """
        ka = KeysAuth(self.path)
        difficulty = ka.get_difficulty()
        self.assertGreaterEqual(difficulty, 0)
        difficulty = ka.get_difficulty("j_AUzb*?V0?g^f9,uI:hewjOTLdu8jn5$%s'a#\iJ8q's~Pa")
        self.assertGreaterEqual(difficulty, 0)

    def test_keys_dir_default2(self):
        self.assertEqual(KeysAuth(self.path).get_keys_dir(), KeysAuth(self.path).get_keys_dir())

    def test_keys_dir_default3(self):
        KeysAuth.get_keys_dir()
        self.assertTrue(path.isdir(KeysAuth._keys_dir))

    def test_keys_dir_setter(self):
        km = KeysAuth(self.path)
        d = path.join(self.path, "blablabla")
        km.set_keys_dir(d)
        self.assertEqual(d, km.get_keys_dir())

    def test_keys_dir_file(self):
        file_ = self.additional_dir_content([1])[0]
        with self.assertRaises(IOError):
            km = KeysAuth(self.path)
            km.set_keys_dir(file_)

    def test_random_number_generator(self):
        with self.assertRaises(ArithmeticError):
            get_random(30, 10)
        self.assertEqual(10, get_random(10, 10))
        for _ in xrange(10):
            a = randint(10, 100)
            b = randint(a + 1, 2 * a)
            r = get_random(a, b)
            self.assertGreaterEqual(r, a)
            self.assertGreaterEqual(b, r)

        for _ in xrange(10):
            r = get_random_float()
            self.assertGreater(r, 0)
            self.assertGreater(1, r)


class TestRSAKeysAuth(TestWithKeysAuth):
    """ Tests for RSAKeysAuth """

    def test_sign_verify(self):
        """ Test signing messages """
        km = RSAKeysAuth(self.path)
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 100
        signature = km.sign(data)
        self.assertTrue(km.verify(signature, data))
        self.assertTrue(km.verify(signature, data, km.public_key))
        km2 = RSAKeysAuth(self.path, "PRIVATE2", "PUBLIC2")
        self.assertTrue(km2.verify(signature, data, km.public_key))
        data2 = "ABBALJL\nafaoawuoauofa\ru0180141mfa\t" * 100
        signature2 = km2.sign(data2)
        self.assertTrue(km.verify(signature2, data2, km2.public_key))
        self.assertFalse(km.verify(signature, data2))
        self.assertFalse(km.verify(signature, [data]))
        self.assertFalse(km.verify(None, data))
        self.assertFalse(km.verify(signature, None))

    def test_encrypt_decrypt_rsa(self):
        """ Test encryption and decryption with RSAKeysAuth """
        from os import urandom
        km = RSAKeysAuth(self.path)
        data = "\x00" + urandom(128)
        self.assertEqual(km.decrypt(km.encrypt(data)), data)
        self.assertEqual(km.decrypt(km.encrypt(data, km.public_key)), data)
        km2 = RSAKeysAuth(self.path)
        data = "\x00" + urandom(128)
        self.assertEqual(km.decrypt(km2.encrypt(data, km.public_key)), data)

    def test_save_load_keys_rsa(self):
        """ Tests for saving and loading keys """
        from os.path import join
        from os import chmod, mkdir
        from golem.core.common import is_windows
        if not path.isdir(self.path):
            mkdir(self.path)
        ek = RSAKeysAuth(self.path)
        pub_key_file = join(self.path, "pub_rsa.key")
        priv_key_file = join(self.path, "priv_rsa.key")
        pub_key = ek.get_public_key().exportKey()
        priv_key = ek._private_key.exportKey()
        self.assertTrue(ek.save_to_files(priv_key_file, pub_key_file))
        with self.assertRaises(TypeError):
            ek.generate_new(None)
        ek.generate_new(5)
        self.assertNotEqual(ek.get_public_key(), pub_key)
        self.assertNotEqual(ek._private_key, priv_key)
        with open(pub_key_file, 'r') as f:
            self.assertEqual(f.read(), pub_key)
        with open(priv_key_file, 'r') as f:
            self.assertEqual(f.read(), priv_key)
        self.assertTrue(ek.load_from_file(priv_key_file))
        self.assertEqual(ek.get_public_key().exportKey(), pub_key)
        self.assertEqual(ek._private_key.exportKey(), priv_key)

        if not is_windows():
            from os import getuid
            if getuid() != 0:
                priv_key_file = join(self.path, "priv_rsa_incorrect.key")
                open(priv_key_file, 'w').close()
                chmod(priv_key_file, 0x700)
                pub_key_file = join(self.path, "pub_rsa_incorrect.key")
                open(pub_key_file, 'w').close()
                chmod(pub_key_file, 0x700)
                self.assertFalse(ek.save_to_files(priv_key_file, pub_key_file))


class TestEllipticalKeysAuth(TestWithKeysAuth):

    def test_elliptical_init(self):
        for i in range(100):
            ek = EllipticalKeysAuth(path.join(self.path), str(random()))
            self.assertEqual(len(ek._private_key), 32)
            self.assertEqual(len(ek.public_key), 64)
            self.assertEqual(len(ek.key_id), 128)

    def test_sign_verify_elliptical(self):
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

    def test_sign_fail_elliptical(self):
        """ Test incorrect signature or data """
        ek = EllipticalKeysAuth(self.path)
        data1 = "qaz123WSX./;'[]"
        data2 = "qaz123WSY./;'[]"
        sig1 = ek.sign(data1)
        sig2 = ek.sign(data2)
        self.assertTrue(ek.verify(sig1, data1))
        self.assertTrue(ek.verify(sig2, data2))
        self.assertFalse(ek.verify(sig1, data2))
        self.assertFalse(ek.verify(sig1, [data1]))
        self.assertFalse(ek.verify(sig2, None))
        self.assertFalse(ek.verify(sig2, data1))
        self.assertFalse(ek.verify(None, data1))

    def test_save_load_keys(self):
        """ Tests for saving and loading keys """
        from os.path import join
        from os import chmod
        from golem.core.common import is_windows
        ek = EllipticalKeysAuth(self.path)
        pub_key_file = join(self.path, "pub.key")
        priv_key_file = join(self.path, "priv.key")
        pub_key = ek.get_public_key()
        priv_key = ek._private_key
        ek.save_to_files(priv_key_file, pub_key_file)
        with self.assertRaises(TypeError):
            ek.generate_new(None)
        ek.generate_new(5)
        self.assertNotEqual(ek.get_public_key(), pub_key)
        self.assertNotEqual(ek._private_key, priv_key)
        with open(pub_key_file, 'rb') as f:
            self.assertEqual(f.read(), pub_key)
        with open(priv_key_file, 'rb') as f:
            self.assertEqual(f.read(), priv_key)
        self.assertTrue(ek.load_from_file(priv_key_file))
        self.assertEqual(ek.get_public_key(), pub_key)
        self.assertEqual(ek._private_key, priv_key)

        if not is_windows():
            from os import getuid
            if getuid() != 0:
                priv_key_file = join(self.path, "priv_incorrect.hey")
                open(priv_key_file, 'w').close()
                chmod(priv_key_file, 0x700)
                pub_key_file = join(self.path, "pub_incorrect.hey")
                open(pub_key_file, 'w').close()
                chmod(pub_key_file, 0x700)
                self.assertFalse(ek.save_to_files(priv_key_file, pub_key_file))

    def test_fixed_sign_verify_elliptical(self):
        public_key = "cdf2fa12bef915b85d94a9f210f2e432542f249b8225736d923fb07ac7ce38fa29dd060f1ea49c75881b6222d26db1c8b0dd1ad4e934263cc00ed03f9a781444"
        private_key = "1aab847dd0aa9c3993fea3c858775c183a588ac328e5deb9ceeee3b4ac6ef078"
        expected_result = "c93a434b74fe2056359fb2e300b2b186f44e5d9bf7b9c47b8f451e449d95cb75525a7a0d10ea01be04040bd57a78607a28a350e08560d584dab5e766515f893700"

        EllipticalKeysAuth.set_keys_dir(self.path)
        ek = EllipticalKeysAuth(self.path)

        ek.public_key = public_key.decode('hex')
        ek._private_key = private_key.decode('hex')
        ek.key_id = ek.cnt_key_id(ek.public_key)
        ek.ecc = ECCx(None, ek._private_key)

        msg = MessageWantToComputeTask(node_name='node_name',
                                       task_id='task_id',
                                       perf_index=2200,
                                       price=5 * 10 ** 18,
                                       max_resource_size=250000000,
                                       max_memory_size=300000000,
                                       num_cores=4,
                                       timestamp=time.time())

        data = msg.get_short_hash()
        signature = ek.sign(data)

        dumped_s = CBORSerializer.dumps(signature)
        loaded_s = CBORSerializer.loads(dumped_s)

        self.assertEqual(signature, loaded_s)

        dumped_d = CBORSerializer.dumps(data)
        loaded_d = CBORSerializer.loads(dumped_d)

        self.assertEqual(data, loaded_d)

        dumped_k = CBORSerializer.dumps(ek.key_id)
        loaded_k = CBORSerializer.loads(dumped_k)

        self.assertEqual(ek.key_id, loaded_k)
        self.assertTrue(ek.verify(loaded_s, loaded_d, ek.key_id))

        src = [1000, signature, time.time(), msg.dict_repr()]
        dumped_l = CBORSerializer.dumps(src)
        loaded_l = CBORSerializer.loads(dumped_l)

        self.assertEqual(src, loaded_l)
        self.assertEqual(signature, loaded_l[1])

        msg_2 = MessageWantToComputeTask(dict_repr=loaded_l[3])

        self.assertEqual(msg.get_short_hash(), msg_2.get_short_hash())
        self.assertTrue(ek.verify(loaded_l[1], msg_2.get_short_hash(), ek.key_id))

        self.assertEqual(type(loaded_l[1]), type(expected_result))
        self.assertEqual(loaded_l[1], expected_result.decode('hex'))

    def test_encrypt_decrypt_elliptical(self):
        """ Test encryption and decryption with EllipticalKeysAuth """
        from os import urandom
        ek = EllipticalKeysAuth(path.join(self.path, str(random())))
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 1000
        enc = ek.encrypt(data)
        self.assertEqual(ek.decrypt(enc), data)
        ek2 = EllipticalKeysAuth(path.join(self.path, str(random())))
        self.assertEqual(ek2.decrypt(ek.encrypt(data, ek2.key_id)), data)
        data2 = "23103"
        self.assertEqual(ek.decrypt(ek2.encrypt(data2, ek.key_id)), data2)
        data3 = "\x00" + urandom(1024)
        ek.generate_new(2)
        self.assertEqual(ek2.decrypt(ek2.encrypt(data3)), data3)
        with self.assertRaises(TypeError):
            ek2.encrypt(None)
