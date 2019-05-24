import os
from os import path, remove
from unittest.mock import Mock, patch, ANY

from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from apps.core.task.coretaskstate import TaskDefinition, TaskState, Options
from apps.core.task.coretask import logger as core_logger
from apps.core.task.coretask import CoreTaskTypeInfo
from apps.rendering.resources.imgrepr import load_img, OpenCVImgRepr, \
    OpenCVError
from apps.rendering.task.renderingtask import (MIN_TIMEOUT, PREVIEW_EXT,
                                               RenderingTask,
                                               RenderingTaskBuilderError,
                                               RenderingTaskBuilder,
                                               SUBTASK_MIN_TIMEOUT)
from apps.core.task.coretask import logger as logger_core
from apps.rendering.task.renderingtask import logger as logger_render

from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture



def _get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return path.join(path.dirname(path.dirname(path.abspath(__file__))),
                     "resources", filename)


class RenderingTaskMock(RenderingTask):

    class ENVIRONMENT_CLASS(object):
        docker_images = []

        def get_id(self):
            return "TEST"

    def query_extra_data(*args, **kwargs):
        pass

    def query_extra_data_for_test_task(self):
        pass


class TestRenderingTask(TestDirFixture, LogTestCase):
    def setUp(self):
        super(TestRenderingTask, self).setUp()
        files = self.additional_dir_content([3])
        task_definition = TaskDefinition()
        task_definition.max_price = 1000
        task_definition.task_id = "xyz"
        task_definition.estimated_memory = 1024
        task_definition.timeout = 3600.0
        task_definition.subtask_timeout = 600
        task_definition.main_scene_file = files[1]
        task_definition.resolution = [800, 600]
        task_definition.output_file = files[2]
        task_definition.output_format = ".png"

        task = RenderingTaskMock(
            task_definition=task_definition,
            total_tasks=100,
            root_path=self.path,
            owner=dt_p2p_factory.Node(),
        )

        dm = DirManager(self.path)
        task.initialize(dm)
        self.task = task

    def test_remove_from_preview(self):
        rt = self.task
        rt.subtasks_given["xxyyzz"] = {"start_task": 2}
       # tmp_dir = get_tmp_path(rt.header.task_id, rt.root_path)
       # makedirs(tmp_dir)
        img = rt._open_preview()
        for i in range(int(round(rt.res_x * rt.scale_factor))):
            for j in range(int(round(rt.res_y * rt.scale_factor))):
                img.set_pixel((i, j), (1, 255, 255))
        img.save_with_extension(rt.preview_file_path, PREVIEW_EXT)
        rt._remove_from_preview("xxyyzz")
        img = rt._open_preview()

        max_x, max_y = 800 - 1, 600 - 1

        assert img.get_pixel((0, 0)) == (1, 255, 255)
        assert img.get_pixel((max_x, 0)) == (1, 255, 255)
        assert img.get_pixel((0, 5)) == (1, 255, 255)
        assert img.get_pixel((max_x, 5)) == (1, 255, 255)

        for i in range(6, 12):
            assert img.get_pixel((0, i)) == (0, 0, 0)
            assert img.get_pixel((max_x, i)) == (0, 0, 0)

        assert img.get_pixel((0, 13)) == (1, 255, 255)
        assert img.get_pixel((max_x, 13)) == (1, 255, 255)
        assert img.get_pixel((0, max_y)) == (1, 255, 255)
        assert img.get_pixel((max_x, max_y)) == (1, 255, 255)


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
        assert preview.get_channels() == OpenCVImgRepr.RGB
        assert preview.get_size() == (800, 600)

        preview = task._open_preview(OpenCVImgRepr.RGB)
        assert preview.get_channels() == OpenCVImgRepr.RGB
        assert preview.get_size() == (800, 600)
        remove(task.preview_file_path)
        preview = task._open_preview(OpenCVImgRepr.RGBA, "PNG")
        assert preview.get_channels() == OpenCVImgRepr.RGBA
        assert preview.get_size() == (800, 600)

    def test_restart_subtask(self):
        task = self.task
        with self.assertLogs(core_logger, level="WARNING"):
            task.restart_subtask("Not existing")

        task.accept_client("node_ABC")
        task.subtasks_given["ABC"] = {'status': SubtaskStatus.starting,
                                      'start_task': 3, "node_id": "node_ABC"}
        task.restart_subtask("ABC")
        assert task.subtasks_given["ABC"]["status"] == SubtaskStatus.restarted

        task.accept_client("node_DEF")
        task.subtasks_given["DEF"] = {'status': SubtaskStatus.finished,
                                      'start_task': 3, "node_id": "node_DEF"}
        task.restart_subtask("DEF")
        assert task.subtasks_given["DEF"]["status"] == SubtaskStatus.restarted

        assert path.isfile(task.preview_file_path)
        assert task.num_tasks_received == -1

        task.accept_client("node_GHI")
        task.subtasks_given["GHI"] = {'status': SubtaskStatus.failure,
                                      'start_task': 3, "node_id": "node_GHI"}
        task.restart_subtask("GHI")
        assert task.subtasks_given["GHI"]["status"] == SubtaskStatus.failure

        task.accept_client("node_JKL")
        task.subtasks_given["JKL"] = {'status': SubtaskStatus.resent,
                                      'start_task': 3, "node_id": "node_JKL"}
        task.restart_subtask("JKL")
        assert task.subtasks_given["JKL"]["status"] == SubtaskStatus.resent

        task.accept_client("node_MNO")
        task.subtasks_given["MNO"] = {'status': SubtaskStatus.restarted,
                                      'start_task': 3, "node_id": "node_MNO"}
        task.restart_subtask("MNO")
        assert task.subtasks_given["MNO"]["status"] == SubtaskStatus.restarted

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
        assert task._get_next_task() is None

    def test_update_task_preview_ioerror(self):
        e = OpenCVError("test message")
        with patch("apps.rendering.resources.imgrepr.OpenCVImgRepr."
                   "from_image_file", side_effect=e), \
                patch("apps.rendering.task.renderingtask.logger") as logger:
            self.task._update_task_preview()
            assert logger.exception.called


class TestRenderingTaskBuilder(TestDirFixture, LogTestCase):
    def test_calculate_total(self):
        definition = RenderingTaskDefinition()
        definition.optimize_total = True
        builder = RenderingTaskBuilder(owner=dt_p2p_factory.Node(),
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
        definition.subtasks_count = 18
        assert builder._calculate_total(defaults) == 18

        definition.subtasks_count = 2
        with self.assertLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 17

        definition.subtasks_count = 3
        with self.assertNoLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 3

        definition.subtasks_count = 34
        with self.assertLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 17

        definition.subtasks_count = 33
        with self.assertNoLogs(logger_render, level="WARNING"):
            assert builder._calculate_total(defaults) == 33

    def test_build_definition_minimal(self):
        # given
        tti = CoreTaskTypeInfo("TESTTASK", RenderingTaskDefinition,
                               Options, RenderingTaskBuilder)
        tti.output_file_ext = 'txt'
        task_dict = {
            'resources': {"file1.png", "file2.txt", 'file3.jpg', 'file4.txt'},
            'compute_on': 'cpu',
            'task_type': 'TESTTASK',
            'subtasks_count': 1
        }

        # when
        definition = RenderingTaskBuilder.build_definition(
            tti, task_dict, minimal=True)

        # then
        assert definition.main_scene_file in ['file2.txt', 'file4.txt']
        assert definition.task_type == "TESTTASK"
        assert definition.resources == {'file1.png', 'file2.txt',
                                        'file3.jpg', 'file4.txt'}


class TestBuildDefinition(TestDirFixture, LogTestCase):
    def setUp(self):
        super().setUp()
        self.tti = CoreTaskTypeInfo("TESTTASK", RenderingTaskDefinition,
                                    Options,
                                    RenderingTaskBuilder)
        self.tti.output_file_ext = 'txt'
        self.task_dict = {
            'resources': {"file1.png", "file2.txt", 'file3.jpg', 'file4.txt'},
            'compute_on': 'cpu',
            'task_type': 'TESTTASK',
            'subtasks_count': 1,
            'options': {'output_path': self.path,
                        'format': 'PNG',
                        'resolution': [800, 600]},
            'name': "NAME OF THE TASK",
            'bid': 0.25,
            'timeout': "01:00:00",
            'subtask_timeout': "00:25:00",
        }

    def test_full(self):
        # when
        definition = RenderingTaskBuilder.build_definition(
            self.tti, self.task_dict)

        # then
        assert definition.name == "NAME OF THE TASK"
        assert definition.max_price == 250000000000000000
        assert definition.timeout == 3600
        assert definition.subtask_timeout == 1500

    def test_timeout_too_short(self):
        # given
        self.task_dict['timeout'] = "00:00:02"
        self.task_dict['subtask_timeout'] = "00:00:01"

        # when
        with self.assertLogs(logger_render, level="WARNING") as log_:
            definition = RenderingTaskBuilder.build_definition(
                self.tti, self.task_dict)

        # then
        assert "Timeout 2 too short for this task. Changing to %d" % \
               MIN_TIMEOUT in log_.output[0]
        assert "Subtask timeout 1 too short for this task. Changing to %d" % \
               SUBTASK_MIN_TIMEOUT in log_.output[1]
        assert definition.timeout == MIN_TIMEOUT
        assert definition.subtask_timeout == SUBTASK_MIN_TIMEOUT

    def test_main_scene_file(self):
        # given
        self.task_dict['resources'] = {
            "/path/to/file1.png",
            "/path/to/file2_longer_name.txt",
            "/path/to/file3.jpg",
            "/path/to/file4.txt",
        }
        self.task_dict['main_scene_file'] = "/path/to/file4.txt"

        # when
        definition = RenderingTaskBuilder.build_definition(
            self.tti, self.task_dict)

        # then
        assert definition.main_scene_file == "/path/to/file4.txt"

    def test_main_scene_no_match(self):
        # given
        self.task_dict['resources'] = {
            "/path/to/file1.png",
            "/path/to/file2.txt",
            "/path/to/file3.jpg",
            "/path/to/file4.txt",
        }
        self.task_dict['main_scene_file'] = "/path/to/file5.txt"

        # when
        definition = RenderingTaskBuilder.build_definition(
            self.tti, self.task_dict)

        # then
        assert definition.resources == {
            "/path/to/file1.png",
            "/path/to/file2.txt",
            "/path/to/file3.jpg",
            "/path/to/file4.txt",
            # because it's added at RenderingTaskDefinition.add_to_resources
            # and it modifies it on windows
            path.normpath("/path/to/file5.txt"),
        }
