import time
from os import path
from random import random, randint

from devp2p.crypto import ECCx

from golem.core.keysauth import KeysAuth, EllipticalKeysAuth, RSAKeysAuth, get_random, get_random_float
from golem.core.simpleserializer import CBORSerializer
from golem.network.transport.message import MessageWantToComputeTask
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

    def test_fixed_sign_verify(self):
        public_key = "cdf2fa12bef915b85d94a9f210f2e432542f249b8225736d923fb07ac7ce38fa29dd060f1ea49c75881b6222d26db1c8b0dd1ad4e934263cc00ed03f9a781444"
        private_key = "1aab847dd0aa9c3993fea3c858775c183a588ac328e5deb9ceeee3b4ac6ef078"
        expected_result = "6c725fa70404abb34b033b76de21684e72c587af400071084a83077344f9163c2a46675f9c510fc4341f25417b26b702f582324f0453bfa7f5418e5e7be2c3fe01"

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

        assert signature == loaded_s

        dumped_d = CBORSerializer.dumps(data)
        loaded_d = CBORSerializer.loads(dumped_d)

        assert data == loaded_d

        dumped_k = CBORSerializer.dumps(ek.key_id)
        loaded_k = CBORSerializer.loads(dumped_k)

        assert ek.key_id == loaded_k
        assert ek.verify(loaded_s, loaded_d, ek.key_id)

        src = [1000, signature, time.time(), msg.dict_repr()]
        dumped_l = CBORSerializer.dumps(src)
        loaded_l = CBORSerializer.loads(dumped_l)

        assert src == loaded_l
        assert signature == loaded_l[1]

        msg_2 = MessageWantToComputeTask(dict_repr=loaded_l[3])

        assert msg.get_short_hash() == msg_2.get_short_hash()
        assert ek.verify(loaded_l[1], msg_2.get_short_hash(), ek.key_id)

        assert type(loaded_l[1]) == type(expected_result)
        print loaded_l
        print expected_result
        assert loaded_l[1] == expected_result.decode('hex')

    def test_encrypt_decrypt(self):
        ek = EllipticalKeysAuth(path.join(self.path, str(random())))
        data = "abcdefgh\nafjalfa\rtajlajfrlajl\t" * 1000
        enc = ek.encrypt(data)
        self.assertEqual(ek.decrypt(enc), data)
        ek2 = EllipticalKeysAuth(path.join(self.path, str(random())))
        self.assertEqual(ek2.decrypt(ek.encrypt(data, ek2.key_id)), data)
        data2 = "23103"
        self.assertEqual(ek.decrypt(ek2.encrypt(data2, ek.key_id)), data2)
