import unittest
from os import makedirs, path

from gnr.renderingdirmanager import get_tmp_path
from gnr.renderingtaskstate import AdvanceRenderingVerificationOptions
from gnr.task.framerenderingtask import get_task_border
from gnr.task.renderingtask import RenderingTask
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.testdirfixture import TestDirFixture


class TestRenderingTask(TestDirFixture):
    def _init_task(self):
        files = self.additional_dir_content([3])
        task = RenderingTask("ABC", "xyz", "10.10.10.10", 1023, "keyid",
                             "DEFAULT", 3600, 600, files[0], set(), self.path,
                             files[1], 100, 800, 600, files[2], files[2],
                             ".png", self.path, 1024, 1000)
        dm = DirManager(self.path)
        task.initialize(dm)
        return task

    def test_paths(self):
        rt = self._init_task()
        res1 = path.join(self.path, "dir1", "dir2", "name1")
        res2 = path.join(self.path, "dir1", "dir2", "name2")
        rt.task_resources = {res1, res2}
        assert rt._get_working_directory() == "../.."

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

    def test_remove_from_preview(self):
        rt = self._init_task()
        rt.subtasks_given["xxyyzz"] = {"start_task": 2, "end_task": 2}
        tmp_dir = get_tmp_path(rt.header.task_id, rt.root_path)
        makedirs(tmp_dir)
        img = rt._open_preview()
        for i in range(int(round(rt.res_x * rt.scale_factor))):
            for j in range(int(round(rt.res_y * rt.scale_factor))):
                img.putpixel((i, j), (1, 255, 255))
        img.save(rt.preview_file_path, "BMP")
        img.close()
        rt._remove_from_preview("xxyyzz")
        img = rt._open_preview()
        assert img.getpixel((0, 0)) == (1, 255, 255)
        assert img.getpixel((0, 2)) == (0, 0, 0)
        assert img.getpixel((200, 3)) == (0, 0, 0)
        assert img.getpixel((199, 4)) == (1, 255, 255)
        assert img.getpixel((100, 16)) == (1, 255, 255)
        img.close()

    def test_has_next_subtask(self):
        rt = self._init_task()
        assert rt.has_next_subtask()

        rt.last_task = rt.total_tasks
        assert not rt.has_next_subtask()

        rt.subtasks_given['task_id'] = dict(status=SubtaskStatus.failure)
        assert rt.has_next_subtask()


class TestGetTaskBorder(unittest.TestCase):

    def test(self):
        border = get_task_border(0, 1, 1, use_frames=False)
        assert len(border) == 1400

        border = get_task_border(0, 1, 1, use_frames=True)
        assert not border

        border = get_task_border(0, 1000, 1000, use_frames=True)
        assert len(border) == 640
