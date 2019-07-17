# pylint: disable=protected-access
import os
import shutil
import time
from random import random, randint
from unittest.mock import patch

from eth_utils import decode_hex, encode_hex
from golem_messages import message
from golem_messages.cryptography import ECCx, privtopub
from golem_messages.factories import tasks as tasks_factory

from golem import testutils
from golem.core.keysauth import (
    KeysAuth, get_random, get_random_float, sha2, WrongPassword)
from golem.tools.testwithreactor import TestWithReactor


class TestKeysAuth(testutils.PEP8MixIn, testutils.TempDirFixture):
    PEP8_FILES = ['golem/core/keysauth.py']

    def _create_keysauth(
            self,
            key_name=None,
            password='') -> KeysAuth:
        if key_name is None:
            key_name = str(random())
        return KeysAuth(
            datadir=self.path,
            private_key_name=key_name,
            password=password,
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

    def test_pubkey_suits_privkey(self):
        ka = self._create_keysauth()
        self.assertEqual(ka.public_key, privtopub(ka._private_key))

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
        assert logger.info.call_count == 1
        assert logger.info.call_args_list[0][0][0] == 'Generating new key pair'
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
        public_key = "0xcdf2fa12bef915b85d94a9f210f2e432542f249b8225736d923fb0"\
                     "7ac7ce38fa29dd060f1ea49c75881b6222d26db1c8b0dd1ad4e934"  \
                     "263cc00ed03f9a781444"
        private_key = "0x1aab847dd0aa9c3993fea3c858775c183a588ac328e5deb9ceeee"\
                      "3b4ac6ef078"

        ek = self._create_keysauth()

        ek.public_key = decode_hex(public_key)
        ek._private_key = decode_hex(private_key)
        ek.key_id = encode_hex(ek.public_key)[2:]
        ek.ecc = ECCx(ek._private_key)

        msg = tasks_factory.WantToComputeTaskFactory()

        dumped_l = msg.serialize(
            sign_as=ek._private_key, encrypt_func=lambda x: x)
        loaded_l = message.Message.deserialize(
            dumped_l, decrypt_func=lambda x: x)

        self.assertEqual(msg.get_short_hash(), loaded_l.get_short_hash())
        self.assertTrue(ek.verify(msg.sig, msg.get_short_hash(), public_key))

    def test_keystore(self):
        key_name = str(random())
        password = 'passwd'

        # Generate new key
        self._create_keysauth(key_name=key_name, password=password)
        # Try to load it, this shouldn't throw
        self._create_keysauth(key_name=key_name, password=password)

        with self.assertRaises(WrongPassword):
            self._create_keysauth(key_name=key_name, password='wrong_pw')
