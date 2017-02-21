import unittest
from os import makedirs, path, remove

from mock import Mock

from apps.core.task.coretaskstate import TaskState
from apps.rendering.task.framerenderingtask import get_task_border, FrameRendererOptions
from apps.rendering.task.renderingtask import RenderingTask
from apps.rendering.task.renderingtaskstate import (AdvanceRenderingVerificationOptions, RenderingTaskDefinition)

from golem.resource.dirmanager import DirManager, get_tmp_path
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
        rt.task_resources = [res1, res2]
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

    def test_update_task_state(self):
        task = self._init_task()
        state = TaskState()
        task.update_task_state(state)
        assert state.extra_data.get("result_preview") is None
        task.preview_task_file_path = "preview_task_file"
        task.preview_file_path = "preview_file"
        task.update_task_state(state)
        assert state.extra_data["result_preview"] == "preview_task_file"
        task.num_tasks_received = task.total_tasks
        task.update_task_state(state)
        assert state.extra_data["result_preview"] == "preview_file"
        task.preview_file_path = None
        task.update_task_state(state)
        assert state.extra_data["result_preview"] == "preview_file"

    def test_has_next_subtask(self):
        rt = self._init_task()
        assert rt.has_next_subtask()

        rt.last_task = rt.total_tasks
        assert not rt.has_next_subtask()

        rt.subtasks_given['task_id'] = dict(status=SubtaskStatus.failure)
        assert rt.has_next_subtask()

    def test_mode_and_ext_in_open_preview(self):
        task = self._init_task()
        preview = task._open_preview()
        assert path.isfile(task.preview_file_path)
        assert preview.mode == "RGB"
        assert preview.size == (267, 200)
        preview.close()

        preview = task._open_preview("RGBA")
        assert preview.mode == "RGB"
        assert preview.size == (267, 200)
        preview.close()
        remove(task.preview_file_path)
        preview = task._open_preview("RGBA", "PNG")
        assert preview.mode == "RGBA"
        assert preview.size == (267, 200)
        preview.close()


class TestGetTaskBorder(unittest.TestCase):

    def test(self):
        subtask = Mock()
        subtask.extra_data = {'start_task': 0, 'end_task': 1}
        definition = RenderingTaskDefinition()
        definition.resolution = [300, 200]
        definition.options = FrameRendererOptions()
        border = get_task_border(subtask, definition, 1)
        assert len(border) == 1400

        definition.options.use_frames = True
        definition.options.frames = range(100)
        border = get_task_border(subtask, definition, 1)
        assert not border

        subtask.extra_data = {'start_task': 0, 'end_task': 1000}
        border = get_task_border(subtask, definition, 1000)
        assert len(border) == 640
