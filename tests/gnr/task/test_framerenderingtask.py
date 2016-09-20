
from PIL import Image
from mock import Mock

from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.testdirfixture import TestDirFixture

from gnr.task.framerenderingtask import FrameRenderingTask
from gnr.renderingdirmanager import get_tmp_path


class TestFrameRenderingTask(TestDirFixture):
    def _get_frame_task(self, use_frames=True):
        files_ = self.additional_dir_content([3])
        task = FrameRenderingTask("ABC", "xyz", "10.10.10.10", 1023, "key_id", "DEFAULT", 3600, 600, files_[0], [],
                                  self.path, files_[1], 3, 800, 600, files_[2], files_[2], "PNG", self.path, 1000,
                                  use_frames, range(6), 15, None)
        dm = DirManager(self.path)
        task.initialize(dm)
        return task

    def test_task(self):
        task = self._get_frame_task()
        assert isinstance(task, FrameRenderingTask)