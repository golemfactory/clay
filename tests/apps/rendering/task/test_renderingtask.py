import ntpath
import os
from os import makedirs, path, remove

from unittest.mock import Mock, patch, ANY

from apps.core.task.coretaskstate import TaskDefinition, TaskState, Options
from apps.core.task.coretask import logger as core_logger
from apps.core.task.coretask import CoreTaskTypeInfo
from apps.rendering.resources.imgrepr import load_img
from apps.rendering.task.renderingtask import (MIN_TIMEOUT, PREVIEW_EXT,
                                               RenderingTask,
                                               RenderingTaskBuilder,
                                               SUBTASK_MIN_TIMEOUT)
from apps.core.task.coretask import logger as logger_core
from apps.rendering.task.renderingtask import logger as logger_render

from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from golem.network.p2p.node import Node

from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture



def _get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return path.join(path.dirname(path.dirname(path.abspath(__file__))), "resources", filename)


class RenderingTaskMock(RenderingTask):

    class ENVIRONMENT_CLASS(object):
        main_program_file = None
        docker_images = []

        def get_id(self):
            return "TEST"

    def __init__(self, main_program_file, *args, **kwargs):
        self.ENVIRONMENT_CLASS.main_program_file = main_program_file
        super(RenderingTaskMock, self).__init__(*args, **kwargs)

    def query_extra_data(*args, **kwargs):
        pass

    def query_extra_data_for_test_task(self):
        pass


class TestInitRenderingTask(TestDirFixture, LogTestCase):
    def test_init(self):
        with self.assertLogs(logger_core, level="WARNING"):
            rt = RenderingTaskMock(main_program_file="notexisting",
                                   task_definition=RenderingTaskDefinition(),
                                   owner=Node(node_name="ABC"),
                                   total_tasks=10,
                                   root_path=self.path
                                   )
        assert isinstance(rt, RenderingTask)
        assert rt.src_code == ""


class TestRenderingTask(TestDirFixture, LogTestCase):
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
            task_definition=task_definition,
            total_tasks=100,
            root_path=self.path,
            owner=Node(
                node_name="ABC",
                pub_addr="10.10.10.10",
                pub_port=1023,
                key="keyid"
            ),
        )

        dm = DirManager(self.path)
        task.initialize(dm)
        self.task = task

    def test_remove_from_preview(self):
        rt = self.task
        rt.subtasks_given["xxyyzz"] = {"start_task": 2, "end_task": 2}
        tmp_dir = DirManager(rt.root_path).get_task_temporary_dir(rt.header.task_id)
       # tmp_dir = get_tmp_path(rt.header.task_id, rt.root_path)
       # makedirs(tmp_dir)
        img = rt._open_preview()
        for i in range(int(round(rt.res_x * rt.scale_factor))):
            for j in range(int(round(rt.res_y * rt.scale_factor))):
                img.putpixel((i, j), (1, 255, 255))
        img.save(rt.preview_file_path, PREVIEW_EXT)
        img.close()
        rt._remove_from_preview("xxyyzz")
        img = rt._open_preview()

        max_x, max_y = 800 - 1, 600 - 1

        assert img.getpixel((0, 0)) == (1, 255, 255)
        assert img.getpixel((max_x, 0)) == (1, 255, 255)
        assert img.getpixel((0, 5)) == (1, 255, 255)
        assert img.getpixel((max_x, 5)) == (1, 255, 255)

        for i in range(6, 12):
            assert img.getpixel((0, i)) == (0, 0, 0)
            assert img.getpixel((max_x, i)) == (0, 0, 0)

        assert img.getpixel((0, 13)) == (1, 255, 255)
        assert img.getpixel((max_x, 13)) == (1, 255, 255)
        assert img.getpixel((0, max_y)) == (1, 255, 255)
        assert img.getpixel((max_x, max_y)) == (1, 255, 255)

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
        assert preview.size == (800, 600)
        preview.close()

        preview = task._open_preview("RGBA")
        assert preview.mode == "RGB"
        assert preview.size == (800, 600)
        preview.close()
        remove(task.preview_file_path)
        preview = task._open_preview("RGBA", "PNG")
        assert preview.mode == "RGBA"
        assert preview.size == (800, 600)
        preview.close()

    def test_restart_subtask(self):
        task = self.task
        with self.assertLogs(core_logger, level="WARNING"):
            task.restart_subtask("Not existing")

        task._accept_client("node_ABC")
        task.subtasks_given["ABC"] = {'status': SubtaskStatus.starting, 'end_task':3,
                                      'start_task': 3, "node_id": "node_ABC"}
        task.restart_subtask("ABC")
        assert task.subtasks_given["ABC"]["status"] == SubtaskStatus.restarted

        task._accept_client("node_DEF")
        task.subtasks_given["DEF"] = {'status': SubtaskStatus.finished, 'end_task': 3,
                                      'start_task': 3, "node_id": "node_DEF"}
        task.restart_subtask("DEF")
        assert task.subtasks_given["DEF"]["status"] == SubtaskStatus.restarted

        assert path.isfile(task.preview_file_path)
        assert task.num_tasks_received == -1

        task._accept_client("node_GHI")
        task.subtasks_given["GHI"] = {'status': SubtaskStatus.failure, 'end_task': 3,
                                      'start_task': 3, "node_id": "node_GHI"}
        task.restart_subtask("GHI")
        assert task.subtasks_given["GHI"]["status"] == SubtaskStatus.failure

        task._accept_client("node_JKL")
        task.subtasks_given["JKL"] = {'status': SubtaskStatus.resent, 'end_task': 3,
                                      'start_task': 3, "node_id": "node_JKL"}
        task.restart_subtask("JKL")
        assert task.subtasks_given["JKL"]["status"] == SubtaskStatus.resent

        task._accept_client("node_MNO")
        task.subtasks_given["MNO"] = {'status': SubtaskStatus.restarted, 'end_task': 3,
                                      'start_task': 3, "node_id": "node_MNO"}
        task.restart_subtask("MNO")
        assert task.subtasks_given["MNO"]["status"] == SubtaskStatus.restarted

    def test_put_collected_files_together_exec_windows(self):

        output_file_name = "out.exr"
        files = ["file_1", "dir_1/file_2", "dir 2/file_3"]
        arg = 'EXR'

        with patch('apps.rendering.task.renderingtask.is_windows',
                   return_value=True), \
                patch('golem.core.fileshelper.is_windows', return_value=True), \
                patch('apps.rendering.task.renderingtask.exec_cmd') as exec_cmd:

            self.task._put_collected_files_together(
                output_file_name, files, arg)

            args = exec_cmd.call_args[0][0]
            assert not args[0].startswith('"')
            assert not args[0].endswith('.exe"')
            assert args[0].endswith('.exe')
            exec_cmd.assert_called_with(
                [ANY, arg, str(self.task.res_x), str(self.task.res_y),
                 '{}'.format(output_file_name)] +
                ['{}'.format(f) for f in files])

    def test_put_collected_files_together_exec_unix(self):
        output_file_name = "out.exr"
        files = ["file_1", "dir_1/file_2", "dir 2/file_3"]
        arg = 'EXR'

        with patch('apps.rendering.task.renderingtask.is_windows',
                   return_value=False), \
                patch('golem.core.fileshelper.is_windows', return_value=False),\
                patch('apps.rendering.task.renderingtask.exec_cmd') as exec_cmd:

            self.task._put_collected_files_together(
                output_file_name, files, arg)

            args = exec_cmd.call_args[0][0]
            assert not args[0].endswith('.exe"')
            assert not args[0].endswith('.exe')
            exec_cmd.assert_called_with(
                [ANY, arg, str(self.task.res_x), str(self.task.res_y),
                 "{}".format(output_file_name)] +
                ["{}".format(f) for f in files])

    def test_get_outer_task(self):
        task = self.task
        task.output_format = "exr"
        assert task._use_outer_task_collector()
        task.output_format = "EXR"
        assert task._use_outer_task_collector()
        task.output_format = "eps"
        assert task._use_outer_task_collector()
        task.output_format = "EPS"
        assert task._use_outer_task_collector()
        task.output_format = "png"
        assert not task._use_outer_task_collector()
        task.output_format = "PNG"
        assert not task._use_outer_task_collector()
        task.output_format = "jpg"
        assert not task._use_outer_task_collector()
        task.output_format = "JPG"
        assert not task._use_outer_task_collector()
        task.output_format = "bmp"
        assert not task._use_outer_task_collector()
        task.output_format = "tga"
        assert not task._use_outer_task_collector()
        task.output_format = "TGA"
        assert not task._use_outer_task_collector()

    def test_get_scene_file_path(self):
        task = self.task
        assert task._get_scene_file_rel_path() == ''

    def test_get_preview_file_path(self):
        assert self.task.get_preview_file_path() is None
        self.task._open_preview()
        assert path.isfile(self.task.get_preview_file_path())

    def test_get_next_task_if_not_tasks(self):
        task = self.task
        task.total_tasks = 10
        task.last_task = 10
        assert task._get_next_task() == (None, None)

    def test_put_collected_files_together(self):
        output_name = self.temp_file_name("output.exr")
        exr1 = _get_test_exr()
        exr2 = _get_test_exr(alt=True)
        assert path.isfile(exr1)
        assert path.isfile(exr2)
        assert load_img(output_name) is None
        self.task.res_x = 10
        self.task.res_y = 20

        self.task._put_collected_files_together(output_name, [exr1, exr2], "paste")
        assert load_img(output_name) is not None

    def test_get_task_collector_path(self):
        assert path.isfile(self.task._get_task_collector_path())

        mock_is_windows = Mock()
        mock_is_windows.return_value = False
        with patch(target="apps.rendering.task.renderingtask.is_windows", new=mock_is_windows):
            linux_path = self.task._get_task_collector_path()
            mock_is_windows.return_value = True

            prefix, exe = os.path.split(linux_path)
            prefix, exe_dir = os.path.split(prefix)
            windows_path = str(self.task._get_task_collector_path())
            assert windows_path.endswith(os.path.join(
                prefix, 'x64', exe_dir, exe + '.exe'
            ))

    def test_update_task_preview_ioerror(self):
        e = IOError("test message")
        with patch("PIL.Image.open", side_effect=e), \
                patch("apps.rendering.task.renderingtask.logger") as logger:
            self.task._update_task_preview()
            assert logger.error.called
            assert logger.error.call_args[0][1] == e


class TestRenderingTaskBuilder(TestDirFixture, LogTestCase):
    def test_calculate_total(self):
        definition = RenderingTaskDefinition()
        definition.optimize_total = True
        builder = RenderingTaskBuilder(owner=Node(node_name="node"),
                                       dir_manager=DirManager(self.path),
                                       task_definition=definition)

        class Defaults(object):
            def __init__(self, default_subtasks=13, min_subtasks=3,
                         max_subtasks=33):
                self.default_subtasks = default_subtasks
                self.min_subtasks = min_subtasks
                self.max_subtasks = max_subtasks

        defaults = Defaults()
        assert builder._calculate_total(defaults) == 13

        defaults.default_subtasks = 17
        assert builder._calculate_total(defaults) == 17

        definition.optimize_total = False
        definition.total_subtasks = 18
        assert builder._calculate_total(defaults) == 18

        definition.total_subtasks = 2
        with self.assertLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 17

        definition.total_subtasks = 3
        with self.assertNoLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 3

        definition.total_subtasks = 34
        with self.assertLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 17

        definition.total_subtasks = 33
        with self.assertNoLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 33

    def test_build_definition(self):
        defaults_mock = Mock()
        defaults_mock.main_program_file = "src_code.py"
        tti = CoreTaskTypeInfo("TESTTASK", RenderingTaskDefinition, defaults_mock,
                               Options, RenderingTaskBuilder)
        tti.output_file_ext = 'txt'
        task_dict = {
                'resources': {"file1.png", "file2.txt", 'file3.jpg',
                              'file4.txt'},
                'task_type': 'TESTTASK',
                'subtasks': 1
        }
        definition = RenderingTaskBuilder.build_definition(
            tti,
            task_dict,
            minimal=True
        )

        assert definition.main_scene_file in ['file2.txt', 'file4.txt']
        assert definition.task_type == "TESTTASK"
        assert definition.resources == {'file1.png', 'file2.txt',
                                        'file3.jpg', 'file4.txt'}

        # Build full definition
        task_dict['options'] = {'output_path': self.path,
                                'format': 'PNG',
                                'resolution': [800, 600]}
        task_dict['name'] = "NAME OF THE TASK"
        task_dict['bid'] = 0.25
        task_dict['timeout'] = "01:00:00"
        task_dict['subtask_timeout'] = "00:25:00"

        definition = RenderingTaskBuilder.build_definition(
            tti,
            task_dict,
            minimal=False
        )
        assert definition.task_name == "NAME OF THE TASK"
        assert definition.max_price == 250000000000000000
        assert definition.full_task_timeout == 3600
        assert definition.subtask_timeout == 1500
        output_file = task_dict['name'] + "." + task_dict['options']['format']
        assert definition.output_file == self.path + os.sep + output_file

        # Timeout too short
        task_dict['timeout'] = "00:00:02"
        task_dict['subtask_timeout'] = "00:00:01"

        with self.assertLogs(logger_render, level="WARNING") as log_:
            definition = RenderingTaskBuilder.build_definition(
                tti,
                task_dict,
                minimal=False
            )

        assert "Timeout 2 too short for this task. Changing to %d" % \
               MIN_TIMEOUT in log_.output[0]
        assert "Subtask timeout 1 too short for this task. Changing to %d" % \
               SUBTASK_MIN_TIMEOUT in log_.output[1]
        assert definition.full_task_timeout == MIN_TIMEOUT
        assert definition.subtask_timeout == SUBTASK_MIN_TIMEOUT

    def test_get_output_path(self):
        td = TaskDefinition()
        td.task_name = "MY task"
        tdict = {'options': {'output_path': '/dir3/dir4', 'format': 'txt'}}
        assert RenderingTaskBuilder.get_output_path(tdict, td) == \
               path.join("/dir3/dir4", "MY task.txt")
