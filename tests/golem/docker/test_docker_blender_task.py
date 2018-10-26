

from os import path
from unittest.mock import Mock

import pytest

from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder, \
    BlenderRenderTask
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.docker.image import DockerImage
from golem.resource.dirmanager import DirManager
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ResultType, TaskHeader
from golem.task.taskcomputer import DockerTaskThread
from golem.task.tasktester import TaskTester
from golem.tools.ci import ci_skip
from .test_docker_task import DockerTaskTestCase


class TestDockerBlenderTaskBase(
        DockerTaskTestCase[BlenderRenderTask, BlenderRenderTaskBuilder]):

    TASK_CLASS = BlenderRenderTask
    TASK_BUILDER_CLASS = BlenderRenderTaskBuilder

    def _test_blender_subtask(self):
        task = self._get_test_task()
        task_thread = self._run_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertEqual(task_thread.error_msg, '')

        # Check the number and type of result files:
        result = task_thread.result
        assert result["result_type"] == ResultType.FILES
        assert len(result["data"]) >= 3
        assert any(path.basename(f) == DockerTaskThread.STDOUT_FILE
                   for f in result["data"])
        assert any(path.basename(f) == DockerTaskThread.STDERR_FILE
                   for f in result["data"])
        assert any(f.endswith(".png") for f in result["data"])


@ci_skip
class TestDockerBlenderCyclesTask(TestDockerBlenderTaskBase):

    TASK_FILE = "docker-blender-cycles-task.json"

    def _run_docker_test_task(self, render_task, timeout=60*5):
        render_task.deadline = timeout_to_deadline(timeout)
        task_computer = TaskTester(render_task, self.path, Mock(), Mock())
        task_computer.run()
        task_computer.tt.join(60.0)
        return task_computer.tt

    def _run_docker_local_comp_task(self, render_task, timeout=60*5):
        render_task.deadline = timeout_to_deadline(timeout)
        local_computer = LocalComputer(
            root_path=self.tempdir, success_callback=Mock(),
            error_callback=Mock(),
            get_compute_task_def=render_task.query_extra_data_for_test_task,
            resources=render_task.task_resources)
        local_computer.run()
        local_computer.tt.join(60)
        return local_computer.tt

    @pytest.mark.slow
    def test_blender_test(self):
        render_task = self._get_test_task()
        tt = self._run_docker_test_task(render_task)
        _, mem = tt.result
        assert mem > 0

        tt = self._run_docker_local_comp_task(render_task)
        assert tt.result

    def test_build(self):
        """ Test building docker blender task """
        from golem.network.p2p.node import Node
        node_name = "some_node"
        task_def = self._get_test_task_definition()
        dir_manager = DirManager(self.path)
        builder = BlenderRenderTaskBuilder(Node(node_name=node_name,
                                                key='dd72b37a1f0c',
                                                pub_addr='1.2.3.4',
                                                pub_port=40102),
                                           task_def, dir_manager)
        task = builder.build()
        assert isinstance(task, BlenderRenderTask)
        assert not task.compositing
        assert not task.use_frames
        assert len(task.frames_given) == 5
        assert isinstance(task.preview_file_path, str)
        assert not task.preview_updaters
        assert task.scale_factor == 0.8
        assert task.src_code
        assert isinstance(task.header, TaskHeader)
        assert task.header.task_id == '7220aa01-ad45-4fb4-b199-ba72b37a1f0c'
        assert task.header.task_owner.key == 'dd72b37a1f0c'
        assert task.header.task_owner.pub_addr == '1.2.3.4'
        assert task.header.task_owner.pub_port == 40102
        assert isinstance(task.header.task_owner, Node)
        assert task.header.subtask_timeout == 1200
        assert task.header.task_owner.node_name == 'some_node'
        assert task.header.resource_size > 0
        assert task.header.environment == 'BLENDER'
        assert task.header.estimated_memory == 0
        assert task.docker_images[0].repository == 'golemfactory/blender'
        assert task.docker_images[0].tag == '1.4'
        assert task.header.max_price == 10.2
        assert not task.header.signature
        assert task.listeners == []
        assert len(task.task_resources) == 1
        assert task.task_resources[0].endswith(
            'scene-Helicopter-27-cycles.blend')
        assert task.total_tasks == 6
        assert task.last_task == 0
        assert task.num_tasks_received == 0
        assert task.subtasks_given == {}
        assert task.num_failed_subtasks == 0
        assert task.timeout == 14400
        assert task.counting_nodes == {}
        assert task.stdout == {}
        assert task.stderr == {}
        assert task.results == {}
        assert task.res_files == {}
        assert path.isdir(task.tmp_dir)

    @pytest.mark.slow
    def test_blender_cycles_subtask(self):
        self._test_blender_subtask()

    def test_blender_subtask_timeout(self):
        task = self._get_test_task()
        task_thread = self._run_task(task, timeout=1)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertTrue(task_thread.error_msg.startswith("Task timed out"))

    def test_wrong_image_repository_specified(self):
        task = self._get_test_task()
        task.docker_images = [DockerImage("%$#@!!!")]
        task_thread = self._run_task(task)
        if task_thread:
            self.assertFalse(task_thread.result)
        self.assertIsInstance(task_thread.error_msg, str)
        self.assertTrue(task_thread.error_msg)

    def test_wrong_image_id_specified(self):
        task = self._get_test_task()
        image = task.docker_images[0]
        task.docker_images = [
            DockerImage(image.repository, image_id="%$#@!!!")]
        task_thread = self._run_task(task)
        if task_thread:
            self.assertFalse(task_thread.result)
        self.assertIsInstance(task_thread.error_msg, str)
        self.assertTrue(task_thread.error_msg)

    def test_blender_subtask_script_error(self):
        task = self._get_test_task()
        # Replace the main script source with another script that will
        # produce errors when run in the task environment:
        task.src_code = 'main :: IO()\nmain = putStrLn "Hello, Haskell World"\n'
        task.main_program_file = path.join(
            path.join(get_golem_path(), "golem"), "node.py")
        task.task_resources = {task.main_program_file, task.main_scene_file}
        task_thread = self._run_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(task_thread.error_msg, str)
        self.assertTrue(
            task_thread.error_msg.startswith("Subtask computation failed"))

    def test_subtask_killed(self):
        task = self._get_test_task()
        # Replace the main script source with another script that will
        # kill itself
        task.src_code = \
            'import os; import signal; os.kill(os.getpid(), signal.SIGKILL)'
        task.main_program_file = path.join(
            path.join(get_golem_path(), "golem"), "node.py")
        task.task_resources = {task.main_program_file, task.main_scene_file}
        task_thread = self._run_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(task_thread.error_msg, str)
        self.assertIn("out-of-memory", task_thread.error_msg)

    def test_blender_scene_file_error(self):
        task = self._get_test_task()
        # Replace scene file with some other, non-blender file:
        task.main_scene_file = task.main_program_file
        task_thread = self._run_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(task_thread.error_msg, str)
        self.assertTrue(task_thread.error_msg)


@ci_skip
class TestDockerBlenderRenderTask(TestDockerBlenderTaskBase):

    TASK_FILE = "docker-blender-render-task.json"

    @pytest.mark.slow
    def test_blender_render_subtask(self):
        self._test_blender_subtask()
