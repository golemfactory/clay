from golem_messages import message
from os import makedirs, path
from random import random, randint
import time
import unittest
from unittest.mock import patch

from golem import testutils
from golem.core.crypto import ECCx
from golem.core.keysauth import EllipticalKeysAuth, \
    get_random, get_random_float, sha2, sha3
from golem.core.simpleserializer import CBORSerializer
from golem.utils import encode_hex, decode_hex


class TestKeysAuth(unittest.TestCase):

    def test_sha(self):
        """ Test sha2 and sha3 methods """
        test_str = "qaz123WSX"
        expected_sha2 = int("0x47b151cede6e6a05140af0da56cb889c40adaf4fddd9f1"
                            "7435cdeb5381be0a62", 16)
        expected_sha3 = ("a99ad773ebfc9712d00a9b9760b879a3aa05054a182d0ba41"
                         "36c5252f5a85203")
        self.assertEqual(sha2(test_str), expected_sha2)
        self.assertEqual(encode_hex(sha3(test_str)), expected_sha3)

    def test_random_number_generator(self):
        with self.assertRaises(ArithmeticError):
            get_random(30, 10)
        self.assertEqual(10, get_random(10, 10))
        for _ in range(10):
            a = randint(10, 100)
            b = randint(a + 1, 2 * a)
            r = get_random(a, b)
            self.assertGreaterEqual(r, a)
            self.assertGreaterEqual(b, r)

        for _ in range(10):
            r = get_random_float()
            self.assertGreater(r, 0)
            self.assertGreater(1, r)


class TestEllipticalKeysAuth(testutils.TempDirFixture):

    def test_init(self):
        for i in range(100):
            ek = EllipticalKeysAuth(path.join(self.path),
                                    private_key_name=str(random()))
            self.assertEqual(len(ek._private_key),
                             EllipticalKeysAuth.PRIV_KEY_LEN)
            self.assertEqual(len(ek.public_key), EllipticalKeysAuth.PUB_KEY_LEN)
            self.assertEqual(len(ek.key_id), EllipticalKeysAuth.KEY_ID_LEN)

    @patch('golem.core.keysauth.logger')
    def test_init_priv_key_wrong_length(self, logger):
        keys_dir = path.join(self.path, 'keys')
        private_key_name = "priv_key"
        private_key_path = path.join(keys_dir, private_key_name)
        public_key_name = "pub_key"
        public_key_path = path.join(keys_dir, public_key_name)

        # given
        makedirs(keys_dir)
        with open(private_key_path, 'wb') as f:
            f.write(b'123')
        with open(public_key_path, 'wb') as f:
            f.write(b'123')

        # when
        EllipticalKeysAuth(self.path,
                           private_key_name=private_key_name,
                           public_key_name=public_key_name)

        # then
        assert logger.warning.called
        with open(private_key_path, 'rb') as f:
            new_priv_key = f.read()
        assert len(new_priv_key) == EllipticalKeysAuth.PRIV_KEY_LEN

    @patch('golem.core.keysauth.logger')
    def test_init_pub_key_wrong_length(self, logger):
        keys_dir = path.join(self.path, 'keys')
        private_key_name = "priv_key"
        private_key_path = path.join(keys_dir, private_key_name)
        public_key_name = "pub_key"
        public_key_path = path.join(keys_dir, public_key_name)

        # given
        makedirs(keys_dir)
        with open(private_key_path, 'wb') as f:
            f.write(b'#'*EllipticalKeysAuth.PRIV_KEY_LEN)
        with open(public_key_path, 'wb') as f:
            f.write(b'123')

        # when
        EllipticalKeysAuth(self.path,
                           private_key_name=private_key_name,
                           public_key_name=public_key_name)

        # then
        assert logger.warning.called
        with open(public_key_path, 'rb') as f:
            new_pub_key = f.read()
        assert len(new_pub_key) == EllipticalKeysAuth.PUB_KEY_LEN

    @patch('golem.core.keysauth.logger')
    def test_key_recreate_on_increased_difficulty(self, logger):
        old_difficulty = 0
        new_difficulty = 8

        assert old_difficulty < new_difficulty  # just in case

        # create key that has difficulty lower than new_difficulty
        ek = EllipticalKeysAuth(self.path, difficulty=old_difficulty)
        while ek.is_difficult(new_difficulty):
            ek.generate_new(old_difficulty)

        assert ek.get_difficulty() >= old_difficulty
        assert ek.get_difficulty() < new_difficulty
        logger.reset_mock()  # just in case

        ek = EllipticalKeysAuth(self.path, difficulty=new_difficulty)

        assert ek.get_difficulty() >= new_difficulty
        assert logger.warning.called

    @patch('golem.core.keysauth.logger')
    def test_key_successful_load(self, logger):
        # given
        ek = EllipticalKeysAuth(self.path)
        priv_key = ek._private_key
        pub_key = ek.public_key
        del ek
        logger.reset_mock()  # just in case

        # when
        ek2 = EllipticalKeysAuth(self.path)

        # then
        assert priv_key == ek2._private_key
        assert pub_key == ek2.public_key
        assert not logger.warning.called

    def test_sign_verify_elliptical(self):
        ek = EllipticalKeysAuth(self.path)
        data = b"abcdefgh\nafjalfa\rtajlajfrlajl\t" * 100
        signature = ek.sign(data)
        self.assertTrue(ek.verify(signature, data))
        self.assertTrue(ek.verify(signature, data, ek.key_id))
        ek2 = EllipticalKeysAuth(path.join(self.path, str(random())))
        self.assertTrue(ek2.verify(signature, data, ek.key_id))
        data2 = b"23103"
        sig = ek2.sign(data2)
        self.assertTrue(ek.verify(sig, data2, ek2.key_id))

    def test_sign_fail_elliptical(self):
        """ Test incorrect signature or data """
        ek = EllipticalKeysAuth(self.path)
        data1 = b"qaz123WSX./;'[]"
        data2 = b"qaz123WSY./;'[]"
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
        public_key = b"cdf2fa12bef915b85d94a9f210f2e432542f249b8225736d923fb0" \
                     b"7ac7ce38fa29dd060f1ea49c75881b6222d26db1c8b0dd1ad4e934" \
                     b"263cc00ed03f9a781444"
        private_key = b"1aab847dd0aa9c3993fea3c858775c183a588ac328e5deb9ceeee" \
                      b"3b4ac6ef078"

        ek = EllipticalKeysAuth(self.path)

        ek.public_key = decode_hex(public_key)
        ek._private_key = decode_hex(private_key)
        ek.key_id = ek._cnt_key_id(ek.public_key)
        ek.ecc = ECCx(None, ek._private_key)

        msg = message.MessageWantToComputeTask(
            node_name='node_name',
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

        dumped_l = msg.serialize(ek.sign, lambda x: ek.encrypt(x, public_key))
        loaded_l = message.Message.deserialize(dumped_l, ek.decrypt)

        self.assertEqual(msg.get_short_hash(), loaded_l.get_short_hash())
        self.assertTrue(ek.verify(msg.sig, msg.get_short_hash(), ek.key_id))

    def test_encrypt_decrypt_elliptical(self):
        """ Test encryption and decryption with EllipticalKeysAuth """
        from os import urandom
        ek = EllipticalKeysAuth(path.join(self.path, str(random())))
        data = b"abcdefgh\nafjalfa\rtajlajfrlajl\t" * 1000
        enc = ek.encrypt(data)
        self.assertEqual(ek.decrypt(enc), data)
        ek2 = EllipticalKeysAuth(path.join(self.path, str(random())))
        self.assertEqual(ek2.decrypt(ek.encrypt(data, ek2.key_id)), data)
        data2 = b"23103"
        self.assertEqual(ek.decrypt(ek2.encrypt(data2, ek.key_id)), data2)
        data3 = b"\x00" + urandom(1024)
        ek.generate_new(2)
        self.assertEqual(ek2.decrypt(ek2.encrypt(data3)), data3)
        with self.assertRaises(TypeError):
            ek2.encrypt(None)

    def test_difficulty(self):
        difficulty = 8
        ek = EllipticalKeysAuth(self.path, difficulty=difficulty)
        # first 8 bits of digest must be 0
        assert sha2(ek.public_key).to_bytes(256, 'big')[0] == 0
        assert ek.get_difficulty() >= difficulty
        assert EllipticalKeysAuth.is_pubkey_difficult(ek.public_key, difficulty)
        assert EllipticalKeysAuth.is_pubkey_difficult(ek.key_id, difficulty)
