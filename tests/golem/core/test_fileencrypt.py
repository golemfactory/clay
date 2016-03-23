import os
import random

from golem.core.fileencrypt import FileHelper, FileEncryptor, AESFileEncryptor
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


class TestAESFileEncryptor(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path, 'node')
        self.res_dir = self.dir_manager.get_task_temporary_dir('test_task')
        self.test_file_path = os.path.join(self.res_dir, 'test_file')
        self.enc_file_path = os.path.join(self.res_dir, 'test_file.enc')

        with open(self.test_file_path, 'wb') as f:
            for i in xrange(0, 100):
                f.write(bytearray(random.getrandbits(8) for _ in xrange(32)))

    def testEncrypt(self):
        secret = FileEncryptor.gen_secret(10, 20)

        if os.path.exists(self.enc_file_path):
            os.remove(self.enc_file_path)

        AESFileEncryptor.encrypt(self.test_file_path,
                                 self.enc_file_path,
                                 secret)

        self.assertTrue(os.path.exists(self.enc_file_path))

    def testDecrypt(self):
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

        self.assertTrue(os.path.getsize(self.test_file_path) ==
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


class TestFileHelper(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)
        self.dir_manager = DirManager(self.path, 'node')
        self.res_dir = self.dir_manager.get_task_temporary_dir('test_task')
        self.test_file_path = os.path.join(self.res_dir, 'test_file')
        open(self.test_file_path, 'w').close()

    def test(self):

        with FileHelper(self.test_file_path, 'r') as f:
            self.assertIsInstance(f, file)

