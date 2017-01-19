import logging
import os

from golem.core.compress import compress, decompress, load, save
from golem.tools.testdirfixture import TestDirFixture


class TestCompress(TestDirFixture):
    def setUp(self):
        super(TestCompress, self).setUp()
        logging.basicConfig(level=logging.DEBUG)

    def test_compress(self):
        text = "12334231234434123452341234"
        c = compress(text)
        self.assertEqual(text, decompress(c))

    def test_load_save(self):
        """ Tests 'load' and 'save' methods without compressing to gzip file """
        self.__test_load_save(False)

    def test_load_save_gzip(self):
        """ Tests 'load' and 'save' methods with compressing to gzip file """
        self.__test_load_save(True)

    def __test_load_save(self, gzip):
        """
        Helper function. Saves data, then loads them and compare
        :param bool gzip:
        """
        text = "123afha  afhakjfh ajkajl 34 2 \n ajrfow 31\r \\ 23443a 4123452341234"
        c = compress(text)
        self.assertEqual(text, decompress(c))
        file_ = os.path.join(self.path, 'tezt.gt')
        save(c, file_, gzip)
        self.assertTrue(os.path.isfile(file_))
        c2 = load(file_, gzip)
        self.assertEqual(text, decompress(c2))
