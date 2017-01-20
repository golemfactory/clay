import os
import random

from golem.core.fileencrypt import FileHelper, FileEncryptor, AESFileEncryptor
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


class TestAESFileEncryptor(TestDirFixture):
    """ Test encryption using AESFileEncryptor """

    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path)
        self.res_dir = self.dir_manager.get_task_temporary_dir('test_task')
        self.test_file_path = os.path.join(self.res_dir, 'test_file')
        self.enc_file_path = os.path.join(self.res_dir, 'test_file.enc')

        with open(self.test_file_path, 'wb') as f:
            for i in xrange(0, 100):
                f.write(bytearray(random.getrandbits(8) for _ in xrange(32)))

    def test_encrypt(self):
        """ Test encryption procedure """
        secret = FileEncryptor.gen_secret(10, 20)

        if os.path.exists(self.enc_file_path):
            os.remove(self.enc_file_path)

        AESFileEncryptor.encrypt(self.test_file_path,
                                 self.enc_file_path,
                                 secret)

        self.assertTrue(os.path.exists(self.enc_file_path))
        with open(self.enc_file_path, 'rb') as f:
            encrypted = f.read()
            self.assertEqual(
                len(encrypted) % AESFileEncryptor.block_size, 0,
                "Incorrect ciphertext size: {}. Should be multiple of {}".format(len(encrypted),
                                                                                 AESFileEncryptor.block_size))

    def test_decrypt(self):
        """ Test decryption procedure """
        secret = FileEncryptor.gen_secret(10, 20)
        decrypted_path = self.test_file_path + ".dec"

        if os.path.exists(self.enc_file_path):
            os.remove(self.enc_file_path)

        AESFileEncryptor.encrypt(self.test_file_path,
                                 self.enc_file_path,
                                 secret)

        AESFileEncryptor.decrypt(self.enc_file_path,
                                 decrypted_path,
                                 secret)

        self.assertEqual(os.path.getsize(self.test_file_path),
                         os.path.getsize(decrypted_path))

        with open(self.test_file_path) as f1, open(decrypted_path) as f2:

            while True:
                chunk1 = f1.read(32)
                chunk2 = f2.read(32)

                if chunk1 != chunk2:
                    raise ValueError("Invalid decrypted file chunk")
                elif not chunk1 and not chunk2:
                    break

        AESFileEncryptor.decrypt(self.enc_file_path,
                                 decrypted_path,
                                 secret + "0")

        decrypted = True

        if os.path.getsize(self.test_file_path) != os.path.getsize(decrypted_path):
            decrypted = False
        else:

            with open(self.test_file_path) as f1, open(decrypted_path) as f2:
                while True:
                    chunk1 = f1.read(32)
                    chunk2 = f2.read(32)

                    if chunk1 != chunk2:
                        decrypted = False
                        break
                    elif not chunk1 and not chunk2:
                        break

        self.assertFalse(decrypted)

    def test_get_key_and_iv(self):
        """ Test helper methods: gen_salt and get_key_and_iv """
        salt = AESFileEncryptor.gen_salt(AESFileEncryptor.block_size)
        self.assertEqual(len(salt), AESFileEncryptor.block_size - AESFileEncryptor.salt_prefix_len)

        secret = FileEncryptor.gen_secret(10, 20)
        self.assertGreaterEqual(len(secret), 10)
        self.assertLessEqual(len(secret), 20)

        key_len = 32
        iv_len = AESFileEncryptor.block_size
        key, iv = AESFileEncryptor.get_key_and_iv(secret, salt, key_len, iv_len)

        self.assertEqual(len(key), key_len)
        self.assertEqual(len(iv), iv_len)


class TestFileHelper(TestDirFixture):
    """ Tests for FileHelper class """

    def setUp(self):
        TestDirFixture.setUp(self)
        self.dir_manager = DirManager(self.path)
        self.res_dir = self.dir_manager.get_task_temporary_dir('test_task')
        self.test_file_path = os.path.join(self.res_dir, 'test_file')
        open(self.test_file_path, 'w').close()

    def test_file_helper(self):
        """ Test opening file with FileHelper """
        mode = 'r'
        # Test opening with file path
        with FileHelper(self.test_file_path, mode) as f:
            self.assertIsInstance(f, file)
            self.assertEqual(f.mode, mode)

        # Test opening with file
        with open(self.test_file_path, mode) as file_:
            with FileHelper(file_, mode) as f:
                self.assertIsInstance(f, file)
                self.assertEqual(f.mode, mode)
