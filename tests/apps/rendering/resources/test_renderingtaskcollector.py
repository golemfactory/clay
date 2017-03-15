import os

from golem.tools.testdirfixture import TestDirFixture

from apps.rendering.resources.renderingtaskcollector import get_exr_files


class TestRenderingTaskCollector(TestDirFixture):
    def test_functions(self):
        assert get_exr_files(self.path) == []
        files = self.additional_dir_content([13])
        os.rename(files[3], files[3] + ".exr")
        os.rename(files[2], files[2] + ".png")
        os.rename(files[7], files[7] + ".EXR")
        os.rename(files[8], files[8] + ".xr")
        assert set(get_exr_files(self.path)) == {files[3] + ".exr", files[7] + ".EXR"}
