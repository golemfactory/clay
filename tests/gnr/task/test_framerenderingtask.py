import time

from golem.tools.testdirfixture import TestDirFixture

from gnr.task.framerenderingtask import FrameRenderingTask


class TestFrameRenderingTask(TestDirFixture):

    def test_total_tasks(self):
        files_ = self.additional_dir_content([2])
        task = FrameRenderingTask("NODE_ABC", "XYZ", "10.10.10.10", 40102, "KEY", "ENV", time.time() + 60 * 5,
                                  60,  files_[0], [], self.path, files_[1], 7, 30, 30, "out", "out2", ".png",
                                  self.path, 1000, True, range(10), 30, None)
        assert isinstance(task, FrameRenderingTask)
        assert task.total_tasks == 7
        task.redundancy = 3
        assert task.total_tasks == 21
