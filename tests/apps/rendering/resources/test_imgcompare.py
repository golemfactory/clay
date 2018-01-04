import os

from PIL import Image

from golem_verificator.rendering.imgcompare import *

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


class TestCompareImgFunctions(TempDirFixture, LogTestCase):

    def test_check_size(self):
        file1 = self.temp_file_name('img.png')
        for y in [10, 11]:
            x = 10
            sample_img = Image.new("RGB", (x, y))
            sample_img.save(file1)
            self.assertTrue(os.path.isfile(file1))
            self.assertTrue(check_size(file1, x, y))
            self.assertFalse(check_size(file1, x, y + 1))
            self.assertFalse(check_size(file1, x, y - 1))
            self.assertFalse(check_size(file1, x + 1, y))