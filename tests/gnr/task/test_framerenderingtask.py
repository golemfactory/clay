from os import path, makedirs

from PIL import Image
from mock import Mock

from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from gnr.task.framerenderingtask import FrameRenderingTask
from gnr.renderingdirmanager import get_tmp_path


class TestFrameRenderingTask(TestDirFixture):
    def _get_frame_task(self, use_frames=True):
        files_ = self.additional_dir_content([3])
        return FrameRenderingTask("ABC", "xyz", "10.10.10.10", 1023, "key_id", "DEFAULT", 3600, 600, files_[0], [],
                                  self.path, files_[1], 3, 800, 600, files_[2], files_[2], "PNG", self.path, 1000,
                                  use_frames, range(6), 15, None)

    def test_verify(self):
        task = self._get_frame_task()
        assert isinstance(task, FrameRenderingTask)
        task.subtasks_given["xxyyzz"] = {"status": SubtaskStatus.starting, "verified": False, 'node_id': "DEF",
                                         "frames": [1, 2]}
        dir_manager = Mock()
        dir_manager.get_task_temporary_dir.return_value = self.path
        assert task.verify_results("xxyyzz", [], dir_manager, 1) == []
        assert task.subtasks_given["xxyyzz"]['verified'] == False
        assert task.counting_nodes.get("DEF") is None
        task.subtasks_given["xxyyzz"] = {"status": SubtaskStatus.starting, "verified": True, 'node_id': "DEF",
                                         "frames": [1, 2]}
        assert task.verify_results("xxyyzz", [], dir_manager, 1) == []
        assert task.subtasks_given["xxyyzz"]['verified'] == False
        assert task.counting_nodes.get("DEF") is None
        task.subtasks_given["xxyyzz"] = {"status": SubtaskStatus.starting, "verified": True, 'node_id': "DEF",
                                         "frames": [1, 2]}
        files = self.additional_dir_content([2])
        assert task.verify_results("xxyyzz", files, dir_manager, 1) == files
        assert task.subtasks_given["xxyyzz"]['verified'] == True
        assert task.counting_nodes.get("DEF") == 1

    def test_accept_results(self):
        task = self._get_frame_task()
        makedirs(get_tmp_path("ABC", "xyz", self.path))
        task.subtasks_given["xxyyzz"] = {"status": SubtaskStatus.starting, "verified": True, 'node_id': "DEF",
                                         "frames": [1, 2], 'start_task': 1, 'parts': 1, 'end_task': 2}
        img = Image.new("RGB", (800, 600), "white")
        files = [path.join(self.path, "file1.PNG"), path.join(self.path, "file2.PNG")]
        img.save(files[0])
        img.save(files[1])
        task.tmp_dir = self.path
        task.accept_results("xxyyzz", files)

        task = self._get_frame_task(False)
        task.subtasks_given["xxyyzz"] = {"status": SubtaskStatus.starting, "verified": True, 'node_id': "DEF",
                                         "frames": [1, 2], 'start_task': 1, 'parts': 1, 'end_task': 2}
        task.accept_results("xxyyzz", files)

        task = self._get_frame_task()
        task.total_tasks = 12
        task.subtasks_given["xxyyzz"] = {"status": SubtaskStatus.starting, "verified": True, 'node_id': "DEF",
                                         "frames": [1, 2], 'start_task': 1, 'parts': 1, 'end_task': 2}
        task.accept_results("xxyyzz", [files[0]])
