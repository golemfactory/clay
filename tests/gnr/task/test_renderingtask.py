from golem.tools.testdirfixture import TestDirFixture

from gnr.task.renderingtask import RenderingTask
from gnr.renderingtaskstate import AdvanceRenderingVerificationOptions


class TestRenderingTask(TestDirFixture):
    def _init_task(self):
        files = self.additional_dir_content([3])
        return RenderingTask("ABC", "xyz", "10.10.10.10", 1023, "keyid",
                             "DEFAULT", 3600, 600, files[0], set(), self.path,
                             files[1], 100, 800, 600, files[2], files[2],
                             ".png", self.path, 1024, 1000)

    def test_box_start(self):
        rt = self._init_task()
        rt.verification_options = AdvanceRenderingVerificationOptions()
        rt.verification_options.box_size = (5, 5)
        sizes = [(24, 12, 44, 20), (0, 0, 800, 600), (10, 150, 12, 152)]
        for size in sizes:
            for i in range(20):
                x, y = rt._get_box_start(*size)
                assert size[0] <= x <= size[2]
                assert size[1] <= y <= size[3]

