import jsonpickle
import logging
from os import makedirs, path
import shutil

from golem.core.common import get_golem_path
from golem.task.taskbase import result_types
from golem.task.taskcomputer import DockerRunnerThread
from golem.task.taskserver import TaskServer
from golem.task.docker.image import DockerImage
import gnr.node
from gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from golem.tools.testwithappconfig import TestWithAppConfig

# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


class TestDockerBlenderTask(TestWithAppConfig):

    TASK_FILE = "docker-blender-test-task.json"

    def setUp(self):
        TestWithAppConfig.setUp(self)
        self.error_msg = None
        self.dirs_to_remove = []
        self.task_computer_send_task_failed = TaskServer.send_task_failed

    def tearDown(self):
        for dir in self.dirs_to_remove:
            shutil.rmtree(dir)
        TaskServer.send_task_failed = self.task_computer_send_task_failed
        TestWithAppConfig.tearDown(self)

    def _test_task_definition(self):
        task_file = path.join(path.dirname(__file__), self.TASK_FILE)
        with open(task_file, "r") as f:
            task_def = jsonpickle.decode(f.read())

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        golem_dir = get_golem_path()

        def set_root_dir(p): return p.replace("$GOLEM_DIR", golem_dir)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_scene_file = set_root_dir(task_def.main_scene_file)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        return task_def

    def _run_docker_task(self, task_def, timeout=0):
        node_name = "0123456789abcdef"
        root_path = get_golem_path()
        task_builder = BlenderRenderTaskBuilder(node_name, task_def, root_path)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda self_: ()
        task_id = render_task.header.task_id
        ctd = render_task.query_extra_data(1.0)

        # Create the computing node
        node = gnr.node.GNRNode()
        node.initialize()

        task_computer = node.client.task_server.task_computer
        resource_dir = task_computer.resource_manager.get_resource_dir(task_id)
        temp_dir = task_computer.resource_manager.get_temporary_dir(task_id)
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources
        common_prefix = path.commonprefix(render_task.task_resources)
        common_prefix = path.dirname(common_prefix)

        for res_file in render_task.task_resources:
            dest_file = path.join(resource_dir,
                                  res_file[len(common_prefix) + 1:])
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

    def test_blender_subtask(self):
        task_def = self._test_task_definition()
        task_thread, error_msg, out_dir = self._run_docker_task(task_def)
        self.assertIsInstance(task_thread, DockerRunnerThread)
        self.assertIsNone(error_msg)

        # Check the number and type of result files:
        result = task_thread.result
        self.assertEqual(result["result_type"], result_types["files"])
        self.assertEqual(len(result["data"]), 3)
        exr_file_present = False
        stdout_file_present = False
        stderr_file_present = False
        for result_file in result["data"]:
            self.assertTrue(result_file.startswith(out_dir))
            self.assertTrue(path.isfile(result_file))
            if result_file.endswith(".exr"):
                exr_file_present = True
            elif result_file.endswith("stdout.log"):
                stdout_file_present = True
            elif result_file.endswith("stderr.log"):
                stderr_file_present = True
        self.assertTrue(exr_file_present)
        self.assertTrue(stdout_file_present)
        self.assertTrue(stderr_file_present)

    def test_blender_subtask_timeout(self):
        task_def = self._test_task_definition()
        task_thread, error_msg, out_dir = self._run_docker_task(task_def, timeout=1)
        self.assertIsInstance(task_thread, DockerRunnerThread)
        self.assertIsInstance(error_msg, str)
        self.assertTrue(error_msg.startswith("Task timed out"))

    def test_wrong_image_repository_specified(self):
        task_def = self._test_task_definition()
        task_def.docker_images = [DockerImage("%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task_def)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

    def test_wrong_image_id_specified(self):
        task_def = self._test_task_definition()
        image = task_def.docker_images[0]
        task_def.docker_images = [DockerImage(image.repository, id = "%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task_def)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

    def test_blender_subtask_script_error(self):
        task_def = self._test_task_definition()
        # Break main script file in task definition; container will be started
        # but blender will not be run.
        task_def.main_program_file = path.join(
            path.dirname(task_def.main_program_file), "blendertask.py")
        task_thread, error_msg, out_dir = self._run_docker_task(task_def)
        self.assertIsInstance(task_thread, DockerRunnerThread)
        self.assertIsInstance(error_msg, str)
        self.assertNotEqual(error_msg, "Wrong result format")
