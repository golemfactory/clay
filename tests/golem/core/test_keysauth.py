import json
import os
from random import random, randint
from unittest.mock import patch

from freezegun import freeze_time
from golem_messages import message
from golem_messages.cryptography import ECCx

from golem import testutils
from golem.core.keysauth import (
    KeysAuth,
    get_random,
    get_random_float,
    sha2,
    WrongPasswordException,
)
from golem.core.simpleserializer import CBORSerializer
from golem.utils import decode_hex
from golem.utils import encode_hex


def make_keystore_json(key, password, **_):
    return {'key': key, 'password': password}


def decode_keystore_json(j, password):
    if password != j['password']:
        raise Exception('Incorrect password')
    return j['key']


# Patch those functions as they are taking quite long to compute
@patch('golem.core.keysauth.make_keystore_json', make_keystore_json)
@patch('golem.core.keysauth.decode_keystore_json', decode_keystore_json)
class TestKeysAuth(testutils.PEP8MixIn, testutils.TempDirFixture):
    PEP8_FILES = ['golem/core/keysauth.py']

    def _create_keysauth(
            self,
            difficulty=0,
            key_name=None,
            password='') -> KeysAuth:
        if key_name is None:
            key_name = str(random())
        return KeysAuth(
            datadir=self.path,
            private_key_name=key_name,
            password=password,
            difficulty=difficulty,
        )

    def test_sha(self):
        """ Test sha2 function"""
        test_str = "qaz123WSX"
        expected_sha2 = int("0x47b151cede6e6a05140af0da56cb889c40adaf4fddd9f1"
                            "7435cdeb5381be0a62", 16)
        self.assertEqual(sha2(test_str), expected_sha2)

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

    def test_init(self):
        for _ in range(100):
            ek = self._create_keysauth()
            self.assertEqual(len(ek._private_key),
                             KeysAuth.PRIV_KEY_LEN)
            self.assertEqual(len(ek.public_key), KeysAuth.PUB_KEY_LEN)
            self.assertEqual(len(ek.key_id), KeysAuth.KEY_ID_LEN)

    @freeze_time("2017-11-23 11:40:27.767804")
    @patch('golem.core.keysauth.logger')
    def test_init_priv_key_wrong_length(self, logger):
        # given
        keys_dir = KeysAuth._get_or_create_keys_dir(self.path)
        key_name = "priv_key"
        key_path = os.path.join(keys_dir, key_name)
        with open(key_path, 'w') as f:
            f.write(json.dumps({'key': '0xdead', 'password': ''}))
        assert os.listdir(keys_dir) == [key_name]

        # when
        self._create_keysauth(key_name=key_name)

        # then
        assert logger.error.call_count == 1
        assert logger.error.call_args[0] == (
            'Wrong loaded private key size: %d.', 2)

        with open(key_path, 'r') as f:
            keystore = f.read()
        keystore = json.loads(keystore)
        keystore['key'] = decode_hex(keystore['key'])
        new_priv_key = decode_keystore_json(keystore, '')
        assert len(new_priv_key) == KeysAuth.PRIV_KEY_LEN
        self.assertCountEqual(
            os.listdir(keys_dir),
            [key_name, "%s_2017-11-23_11-40-27_767804.bak" % key_name]
        )

    def test_difficulty(self):
        difficulty = 5
        ek = self._create_keysauth(difficulty)
        assert difficulty <= ek.difficulty
        assert ek.difficulty == KeysAuth.get_difficulty(ek.key_id)

    def test_get_difficulty(self):
        difficulty = 8
        ek = self._create_keysauth(difficulty)
        # first 8 bits of digest must be 0
        assert sha2(ek.public_key).to_bytes(256, 'big')[0] == 0
        assert KeysAuth.get_difficulty(ek.key_id) >= difficulty
        assert KeysAuth.is_pubkey_difficult(ek.public_key, difficulty)
        assert KeysAuth.is_pubkey_difficult(ek.key_id, difficulty)

    @freeze_time("2017-11-23 11:40:27.767804")
    @patch('golem.core.keysauth.logger')
    def test_key_backup_and_recreate_on_increased_difficulty(self, logger):
        # given
        old_difficulty = 0
        new_difficulty = 7
        priv_key = str(random())[2:]
        keys_dir = KeysAuth._get_or_create_keys_dir(self.path)

        assert old_difficulty < new_difficulty  # just in case

        keys_dir = KeysAuth._get_or_create_keys_dir(self.path)
        # create key that has difficulty lower than new_difficulty
        while True:
            ek = self._create_keysauth(old_difficulty, priv_key)
            if not ek.is_difficult(new_difficulty):
                break
            os.rmdir(keys_dir)  # to enable keys regeneration

        assert KeysAuth.get_difficulty(ek.key_id) >= old_difficulty
        assert KeysAuth.get_difficulty(ek.key_id) < new_difficulty
        logger.reset_mock()  # just in case

        # when
        ek = self._create_keysauth(new_difficulty, priv_key)

        # then
        assert KeysAuth.get_difficulty(ek.key_id) >= new_difficulty
        assert logger.warning.call_count == 1
        assert logger.warning.call_args[0][0] == \
            'Loaded key is not difficult enough.'
        self.assertCountEqual(
            os.listdir(keys_dir),
            [priv_key, "%s_2017-11-23_11-40-27_767804.bak" % priv_key],
        )

    def test_save_keys(self):
        # given
        keys_dir = KeysAuth._get_or_create_keys_dir(self.path)
        assert os.listdir(keys_dir) == []  # empty dir
        key_name = 'priv'

        # when
        self._create_keysauth(key_name=key_name)

        # then
        self.assertCountEqual(os.listdir(keys_dir), [key_name])

    @patch('golem.core.keysauth.logger')
    def test_key_successful_load(self, logger):
        # given
        priv_key = str(random())
        ek = self._create_keysauth(key_name=priv_key)
        private_key = ek._private_key
        public_key = ek.public_key
        del ek
        assert logger.info.call_count == 2
        assert logger.info.call_args_list[0][0][0] == 'Generating new key pair'
        assert logger.info.call_args_list[1][0][0] == 'Keys generated in %.2fs'
        logger.reset_mock()  # just in case

        # when
        ek2 = self._create_keysauth(key_name=priv_key)

        # then
        assert private_key == ek2._private_key
        assert public_key == ek2.public_key
        assert not logger.warning.called

    def test_sign_verify(self):
        ek = self._create_keysauth()
        data = b"abcdefgh\nafjalfa\rtajlajfrlajl\t" * 100
        signature = ek.sign(data)
        self.assertTrue(ek.verify(signature, data))
        self.assertTrue(ek.verify(signature, data, ek.key_id))
        ek2 = self._create_keysauth()
        self.assertTrue(ek2.verify(signature, data, ek.key_id))
        data2 = b"23103"
        sig = ek2.sign(data2)
        self.assertTrue(ek.verify(sig, data2, ek2.key_id))

    @patch('golem.core.keysauth.logger')
    def test_sign_verify_fail(self, logger):
        """ Test incorrect signature or data """
        # given
        data1 = b"qaz123WSX./;'[]"
        data2 = b"qaz123WSY./;'[]"

        # when
        ek = self._create_keysauth()
        sig1 = ek.sign(data1)
        sig2 = ek.sign(data2)

        # then
        self.assertTrue(ek.verify(sig1, data1))
        self.assertTrue(ek.verify(sig2, data2))
        self.assertFalse(ek.verify(sig1, data2))
        self.assertFalse(ek.verify(sig1, [data1]))
        self.assertFalse(ek.verify(sig2, None))
        self.assertFalse(ek.verify(sig2, data1))
        self.assertFalse(ek.verify(None, data1))
        assert logger.error.call_count == 5
        for args in logger.error.call_args_list:
            assert args[0][0].startswith('Cannot verify signature: ')

    def test_fixed_sign_verify(self):  # pylint: disable=too-many-locals
        public_key = b"cdf2fa12bef915b85d94a9f210f2e432542f249b8225736d923fb0" \
                     b"7ac7ce38fa29dd060f1ea49c75881b6222d26db1c8b0dd1ad4e934" \
                     b"263cc00ed03f9a781444"
        private_key = b"1aab847dd0aa9c3993fea3c858775c183a588ac328e5deb9ceeee" \
                      b"3b4ac6ef078"

        ek = self._create_keysauth()

        ek.public_key = decode_hex(public_key)
        ek._private_key = decode_hex(private_key)
        ek.key_id = encode_hex(ek.public_key)
        ek.ecc = ECCx(ek._private_key)

        msg = message.WantToComputeTask(node_name='node_name',
                                        task_id='task_id',
                                        perf_index=2200,
                                        price=5 * 10 ** 18,
                                        max_resource_size=250000000,
                                        max_memory_size=300000000,
                                        num_cores=4)

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
        self.assertTrue(ek.verify(loaded_s, loaded_d, ek.public_key))

        dumped_l = msg.serialize(ek.sign, lambda x: ek.encrypt(x, public_key))
        loaded_l = message.Message.deserialize(dumped_l, ek.decrypt)

        self.assertEqual(msg.get_short_hash(), loaded_l.get_short_hash())
        self.assertTrue(ek.verify(msg.sig, msg.get_short_hash(), public_key))

    def test_encrypt_decrypt(self):
        """ Test encryption and decryption with KeysAuth """
        ek = self._create_keysauth()
        data = b"abcdefgh\nafjalfa\rtajlajfrlajl\t" * 1000
        enc = ek.encrypt(data)
        self.assertEqual(ek.decrypt(enc), data)
        ek2 = self._create_keysauth()
        self.assertEqual(ek2.decrypt(ek.encrypt(data, ek2.key_id)), data)
        data2 = b"23103"
        self.assertEqual(ek.decrypt(ek2.encrypt(data2, ek.key_id)), data2)
        data3 = b"\x00" + os.urandom(1024)
        ek2 = self._create_keysauth(difficulty=2)
        self.assertEqual(ek2.decrypt(ek2.encrypt(data3)), data3)
        with self.assertRaises(TypeError):
            ek2.encrypt(None)


class TestKeysAuthKeystore(testutils.TempDirFixture):
    def test_keystore(self):
        key_name = str(random())
        password = 'passwd'

        # Generate new key
        KeysAuth(
            datadir=self.path,
            private_key_name=key_name,
            password=password,
        )
        # Try to load it, this shouldn't throw
        KeysAuth(
            datadir=self.path,
            private_key_name=key_name,
            password=password,
        )

        with self.assertRaises(WrongPasswordException):
            KeysAuth(
                datadir=self.path,
                private_key_name=key_name,
                password='wrongpassword',
            )
