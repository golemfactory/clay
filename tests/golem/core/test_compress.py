import logging
import os

from golem.core.compress import compress, decompress, load, save
from golem.tools.testdirfixture import TestDirFixture


class TestCompress(TestDirFixture):
    def setUp(self):
        super(TestCompress, self).setUp()
        logging.basicConfig(level=logging.DEBUG)

    def testCompress(self):
        text = "12334231234434123452341234"
        c = compress(text)
        self.assertEqual(text, decompress(c))

    def testLoadSave(self):
        text = "123afha  afhakjfh ajkajl 34 2 \n ajrfow 31\r \\ 23443a 4123452341234"
        c = compress(text)
        self.assertEqual(text, decompress(c))
        file_ = os.path.join(self.path, 'tezt.gt')
        save(c, file_)
        c2 = load(file_)
        self.assertEqual(text, decompress(c2))
