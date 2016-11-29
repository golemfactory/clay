import os
from PIL import Image

from golem.testutils import TempDirFixture

from apps.rendering.resources.imgrepr import verify_img


class TestImgrepr(TempDirFixture):
    def test_verify_img(self):
        file1 = self.temp_file_name('img.png')
        for y in range(100, 200):
            x = 100
            sample_img = Image.new("RGB", (x, y))
            sample_img.save(file1)
            self.assertTrue(os.path.isfile(file1))
            self.assertTrue(verify_img(file1, x, y))
            self.assertTrue(verify_img(file1, x, y + 1))
            self.assertTrue(verify_img(file1, x, y - 1))
            self.assertFalse(verify_img(file1, x + 1, y))
