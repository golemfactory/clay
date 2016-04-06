import logging
import shutil
from os import makedirs, path

import jsonpickle
from mock import Mock

import gnr.node
from gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from gnr.task.tasktester import TaskTester
from golem.core.common import get_golem_path
from golem.docker.image import DockerImage
from golem.task.taskbase import result_types
from golem.task.taskcomputer import DockerTaskThread
from golem.task.taskserver import TaskServer
from golem.tools.testdirfixture import TestDirFixture
from test_docker_image import DockerTestCase

# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


class TestDockerBlenderTask(TestDirFixture, DockerTestCase):

    CYCLES_TASK_FILE = "docker-blender-cycles-task.json"
    BLENDER_TASK_FILE = "docker-blender-render-task.json"

    def setUp(self):
        super(TestDockerBlenderTask, self).setUp()
        self.error_msg = None
        self.dirs_to_remove = []
        self.task_computer_send_task_failed = TaskServer.send_task_failed

    def tearDown(self):
        for dir in self.dirs_to_remove:
            shutil.rmtree(dir)
        TaskServer.send_task_failed = self.task_computer_send_task_failed
        super(TestDockerBlenderTask, self).tearDown()

    def _load_test_task_definition(self, task_file):
        task_file = path.join(path.dirname(__file__), task_file)
        with open(task_file, "r") as f:
            task_def = jsonpickle.decode(f.read())

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        golem_dir = get_golem_path()

        def set_root_dir(p):
            return p.replace("$GOLEM_DIR", golem_dir)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_scene_file = set_root_dir(task_def.main_scene_file)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        return task_def

    def _create_test_task(self, task_file=CYCLES_TASK_FILE):
        task_def = self._load_test_task_definition(task_file)
        node_name = "0123456789abcdef"
        root_path = get_golem_path()
        task_builder = BlenderRenderTaskBuilder(node_name, task_def, root_path)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda self_: ()
        return render_task

    def _run_docker_task(self, render_task, timeout=0):
        task_id = render_task.header.task_id
        ctd = render_task.query_extra_data(1.0)

        # Create the computing node
        node = gnr.node.GNRNode(datadir=self.path)
        node.initialize()

        task_computer = node.client.task_server.task_computer
        resource_dir = task_computer.resource_manager.get_resource_dir(task_id)
        temp_dir = task_computer.resource_manager.get_temporary_dir(task_id)
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources
        all_resources = render_task.task_resources.copy()
        all_resources.add(render_task.main_program_file)
        common_prefix = path.commonprefix(all_resources)
        common_prefix = path.dirname(common_prefix)

        for res_file in all_resources:
            dest_file = path.join(resource_dir,
                                  path.relpath(res_file, common_prefix))
            dest_dirname = path.dirname(dest_file)
            if not path.exists(dest_dirname):
                makedirs(dest_dirname)
            shutil.copyfile(res_file, dest_file)

        def send_task_failed(self_, subtask_id, task_id, error_msg, *args):
            self.error_msg = error_msg

        TaskServer.send_task_failed = send_task_failed

        # Start task computation
        task_computer.task_given(ctd, timeout)
        result = task_computer.resource_given(ctd.task_id)
        self.assertTrue(result)

        # Thread for task computation should be created by now
        task_thread = None
        with task_computer.lock:
            if task_computer.current_computations:
                task_thread = task_computer.current_computations[0]

        if task_thread:
            task_thread.join(60.0)

        return task_thread, self.error_msg, temp_dir

    def _run_docker_test_task(self, render_task, timeout=0):
        task_computer = TaskTester(render_task, self.path, Mock())
        task_computer.run()
        task_computer.tt.join(60.0)
        return task_computer.tt

    def _test_blender_subtask(self, task_file):
        task = self._create_test_task(task_file)
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsNone(error_msg)

        # Check the number and type of result files:
        result = task_thread.result
        self.assertEqual(result["result_type"], result_types["files"])
        self.assertGreaterEqual(len(result["data"]), 3)
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDOUT_FILE for f in result["data"]))
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDERR_FILE for f in result["data"]))
        self.assertTrue(
            any(f.endswith(".png") for f in result["data"]))

    def test_blender_test(self):
        render_task = self._create_test_task()
        tt = self._run_docker_test_task(render_task)
        result, mem = tt.result
        assert mem > 0

    def test_blender_render_subtask(self):
        self._test_blender_subtask(self.BLENDER_TASK_FILE)

    def test_blender_cycles_subtask(self):
        self._test_blender_subtask(self.CYCLES_TASK_FILE)

    def test_blender_subtask_timeout(self):
        task = self._create_test_task()
        task_thread, error_msg, out_dir = \
            self._run_docker_task(task, timeout=1)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(error_msg, str)
        self.assertTrue(error_msg.startswith("Task timed out"))

    def test_wrong_image_repository_specified(self):
        task = self._create_test_task()
        task.header.docker_images = [DockerImage("%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

    def test_wrong_image_id_specified(self):
        task = self._create_test_task()
        image = task.header.docker_images[0]
        task.header.docker_images = [
            DockerImage(image.repository, image_id="%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

    def test_blender_subtask_script_error(self):
        task = self._create_test_task()
        # Replace the main script source with another script that will
        # produce errors when run in the task environment:
        task.src_code = 'main :: IO()\nmain = putStrLn "Hello, Haskell World"\n'
        task.main_program_file = path.join(
            path.join(get_golem_path(), "gnr"), "node.py")
        task.task_resources = {task.main_program_file, task.main_scene_file}
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(error_msg, str)
        self.assertTrue(error_msg.startswith("Subtask computation failed"))

    def test_blender_scene_file_error(self):
        task = self._create_test_task()
        # Replace scene file with some other, non-blender file:
        task.main_scene_file = task.main_program_file
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(error_msg, str)
