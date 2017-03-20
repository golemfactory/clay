import os

from PIL import Image

from golem.tools.testdirfixture import TestDirFixture

from apps.rendering.resources.renderingtaskcollector import RenderingTaskCollector
from apps.rendering.resources.imgrepr import compare_pil_imgs, advance_verify_img, load_img


def make_test_img(img_path, size=(10, 10), color=(255, 0, 0)):
    img = Image.new('RGB', size, color)
    img.save(img_path)
    img.close()


def _get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


class TestRenderingTaskCollector(TestDirFixture):
    def test_init(self):
        collector = RenderingTaskCollector()
        assert not collector.paste
        assert collector.width is None
        assert collector.height is None
        assert collector.accepted_img_files == []
        assert collector.accepted_alpha_files == []

    def test_add_files(self):
        collector = RenderingTaskCollector()
        for i in range(10):
            collector.add_img_file("file{}.png".format(i))
            collector.add_alpha_file("file_alpha_{}.png".format(i))

        assert len(collector.accepted_img_files) == 10
        assert len(collector.accepted_alpha_files) == 10

    def test_finalize(self):
        collector = RenderingTaskCollector(paste=True)
        assert collector.finalize() is None

        img1 = self.temp_file_name("img1.png")
        make_test_img(img1)

        collector.add_img_file(img1)
        final_img = collector.finalize()
        assert isinstance(final_img, Image.Image)
        assert final_img.size == (10, 10)
        img2 = self.temp_file_name("img2.png")
        final_img.save(img2)

        assert compare_pil_imgs(img1, img2)
        collector.add_img_file(img2)
        final_img = collector.finalize()
        assert isinstance(final_img, Image.Image)
        img3 = self.temp_file_name("img3.png")
        final_img.save(img3)

        assert final_img.size == (10, 20)
        assert advance_verify_img(img3, 10, 20, (0, 0), (10, 10), img1, (0, 0))

        collector = RenderingTaskCollector(paste=False, width=10, height=10)
        collector.add_img_file(img1)

        make_test_img(img2, color=(0, 255, 0))
        collector.add_img_file(img2)
        make_test_img(img3, color=(0, 0, 255))
        final_img = collector.finalize()
        assert final_img.size == (10, 10)

    def test_finalize_alpha(self):
        collector = RenderingTaskCollector()

        collector.add_alpha_file(_get_test_exr())
        collector.add_alpha_file(_get_test_exr(alt=True))

        img_path = self.temp_file_name("img1.png")
        make_test_img(img_path)
        img_repr = load_img(img_path)

        collector.finalize_alpha(img_repr.img)

    def test_finalize_exr(self):
        collector = RenderingTaskCollector()
        collector.add_img_file(_get_test_exr())
        collector.add_img_file(_get_test_exr(alt=True))
        img = collector.finalize()
        assert isinstance(img, Image.Image)
        assert img.size == (10, 10)

        collector = RenderingTaskCollector(paste=True)
        collector.add_img_file(_get_test_exr())
        collector.add_img_file(_get_test_exr(alt=True))
        img = collector.finalize()
        assert isinstance(img, Image.Image)
        assert img.size == (10, 20)
