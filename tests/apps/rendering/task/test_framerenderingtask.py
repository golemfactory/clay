
from golem.resource.dirmanager import DirManager

from golem.tools.testdirfixture import TestDirFixture

from apps.rendering.task.framerenderingtask import get_frame_name


class TestFrameRenderingTask(TestDirFixture):
    def test_get_frame_name(self):
        assert get_frame_name("ABC", "png", 124) == "ABC0124.png"
        assert get_frame_name("QWERT_", "EXR", 13) == "QWERT_0013.EXR"
        assert get_frame_name("IMAGE_###", "jpg", 4) == "IMAGE_004.jpg"
        assert get_frame_name("IMAGE_###_VER_131", "JPG", 23) == "IMAGE_023_VER_131.JPG"
        assert get_frame_name("IMAGE_###_ABC", "exr", 1023) == "IMAGE_1023_ABC.exr"
        assert get_frame_name("##_#####", "png", 3) == "##_00003.png"
        assert get_frame_name("#####_###", "PNG", 27) == "#####_027.PNG"
