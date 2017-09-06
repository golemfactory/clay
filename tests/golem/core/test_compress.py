import logging
import os

from golem.core.compress import compress, decompress
from golem.tools.testdirfixture import TestDirFixture


class TestCompress(TestDirFixture):
    def setUp(self):
        super(TestCompress, self).setUp()
        logging.basicConfig(level=logging.DEBUG)

    def test_compress(self):
        text = b"12334231234434123452341234"
        c = compress(text)
        self.assertEqual(text, decompress(c))
