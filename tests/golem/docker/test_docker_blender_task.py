import jsonpickle
import logging
from os import makedirs, path
import shutil
import unittest

from golem.core.common import get_golem_path
from golem.task.taskbase import result_types
from golem.task.taskcomputer import DockerRunnerThread
from golem.task.taskserver import TaskServer
from golem.task.docker.image import DockerImage
import gnr.node
from gnr.task.blenderrendertask import BlenderRenderTaskBuilder


# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


TASK_FILE = "docker-blender-test-task.json"


class TestDockerBlenderTask(unittest.TestCase):

    def setUp(self):
        self.error_msg = None
        self.dirs_to_remove = []
        self.task_computer_send_task_failed = TaskServer.send_task_failed

    def tearDown(self):
        for dir in self.dirs_to_remove:
            shutil.rmtree(dir)
        TaskServer.send_task_failed = self.task_computer_send_task_failed

    def _test_task_definition(self):
        with open(TASK_FILE, "r") as f:
            task_def = jsonpickle.decode(f.read())
        return task_def

    def _run_docker_task(self, task_def):
        node_name = "0123456789abcdef"
        root_path = get_golem_path()
        task_builder = BlenderRenderTaskBuilder(node_name, task_def, root_path)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda s: ()
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

        def send_task_failed(self_, subtask_id, task_id, error_msg_, *args):
            # global error_msg
            self.error_msg = error_msg_

        TaskServer.send_task_failed = send_task_failed

        # Start task computation
        subtask_timeout = 600
        task_computer.task_given(ctd, subtask_timeout)
        result = task_computer.resource_given(ctd.task_id)
        self.assertTrue(result)

        # Thread for task computation should be created by now
        # self.assertEqual(len(task_computer.current_computations), 1)
        task_thread = None
        if task_computer.current_computations:
            task_thread = task_computer.current_computations[0]
            task_thread.join(60.0)

        return task_thread, self.error_msg, temp_dir

    def test_blender_subtask(self):
        task_def = self._test_task_definition()
        task_thread, error_msg, out_dir = self._run_docker_task(task_def)
        self.assertIsInstance(task_thread, DockerRunnerThread)
        self.assertIsNone(error_msg)

        # Check if the result is there
        result = task_thread.result
        self.assertEqual(result["result_type"], result_types["files"])
        result_file = result["data"][0]
        self.assertTrue(result_file.startswith(out_dir))
        self.assertTrue(path.isfile(result_file))

    def test_wrong_image_repository_specified(self):
        task_def = self._test_task_definition()
        # image = task_def.docker_images[0]
        task_def.docker_images = [DockerImage("%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task_def)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

