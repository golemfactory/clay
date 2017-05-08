import os

from PIL import Image

from apps.blender.resources.imgcompare import check_size

from golem.testutils import TempDirFixture


class TestCompareImgFunctions(TempDirFixture):
    def test_check_size(self):
        file1 = self.temp_file_name('img.png')
        for y in [10, 11]:
            x = 10
            sample_img = Image.new("RGB", (x, y))
            sample_img.save(file1)
            self.assertTrue(os.path.isfile(file1))
            self.assertTrue(check_size(file1, x, y))
            self.assertTrue(check_size(file1, x, y + 1))
            self.assertTrue(check_size(file1, x, y - 1))
            self.assertFalse(check_size(file1, x + 1, y))

        self.assertFalse(check_size("not an image", 10, 10))
