import unittest
from os import makedirs, path, remove

import mock
from mock import Mock

from apps.core.task.coretaskstate import TaskDefinition
from apps.core.task.coretaskstate import TaskState
from apps.rendering.task.framerenderingtask import get_task_border, FrameRendererOptions
from apps.rendering.task.renderingtask import RenderingTask
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from golem.resource.dirmanager import DirManager, get_tmp_path
from golem.tools.testdirfixture import TestDirFixture


class RenderingTaskMock(RenderingTask):
    class ENVIRONMENT_CLASS(object):
        main_program_file = None
        docker_images = []

        def get_id(self):
            return "TEST"

    def __init__(self, main_program_file, *args, **kwargs):
        self.ENVIRONMENT_CLASS.main_program_file = main_program_file
        super(RenderingTaskMock, self).__init__(*args, **kwargs)


class TestRenderingTask(TestDirFixture):
    def setUp(self):
        super(TestRenderingTask, self).setUp()
        files = self.additional_dir_content([3])
        task_definition = TaskDefinition()
        task_definition.max_price = 1000
        task_definition.task_id = "xyz"
        task_definition.estimated_memory = 1024
        task_definition.full_task_timeout = 3600
        task_definition.subtask_timeout = 600
        task_definition.main_scene_file=files[1]
        task_definition.resolution = [800, 600]
        task_definition.output_file = files[2]
        task_definition.output_format = ".png"

        task = RenderingTaskMock(
            main_program_file=files[0],
            node_name="ABC",
            task_definition=task_definition,
            total_tasks=100,
            root_path=self.path,
            owner_address="10.10.10.10",
            owner_port=1023,
            owner_key_id="keyid",
        )

        dm = DirManager(self.path)
        task.initialize(dm)
        self.task = task

    def test_paths(self):
        rt = self.task
        res1 = path.join(self.path, "dir1", "dir2", "name1")
        res2 = path.join(self.path, "dir1", "dir2", "name2")
        rt.task_resources = [res1, res2]
        assert rt._get_working_directory() == "../.."

    def test_remove_from_preview(self):
        rt = self.task
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
        task = self.task
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

    def test_mode_and_ext_in_open_preview(self):
        task = self.task
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

    def test_put_collected_files_together(self):

        output_file_name = "out.exr"
        files = ["file_1", "dir_1/file_2", "dir 2/file_3"]
        arg = 'EXR'

        def assert_command_line(exec_cmd):
            args = exec_cmd.call_args[0][0]
            assert args[1] == arg
            assert args[2] == str(self.task.res_x)
            assert args[3] == str(self.task.res_y)
            assert args[4] == '"{}"'.format(output_file_name)
            assert all([af == '"{}"'.format(f) for af, f in zip(args[5:], files)])

        with mock.patch('apps.rendering.task.renderingtask.is_windows', side_effect=lambda: True), \
             mock.patch('apps.rendering.task.renderingtask.exec_cmd') as exec_cmd:

            self.task._put_collected_files_together(output_file_name, files, arg)

            args = exec_cmd.call_args[0][0]
            assert_command_line(exec_cmd)
            assert args[0].endswith('.exe')

        with mock.patch('apps.rendering.task.renderingtask.is_windows', side_effect=lambda: False), \
             mock.patch('apps.rendering.task.renderingtask.exec_cmd') as exec_cmd:

            self.task._put_collected_files_together(output_file_name, files, arg)

            args = exec_cmd.call_args[0][0]
            assert_command_line(exec_cmd)
            assert not args[0].endswith('.exe')


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
