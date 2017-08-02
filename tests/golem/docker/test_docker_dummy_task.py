import logging
import os
import shutil
from os import makedirs, path, remove

import jsonpickle as json
from mock import Mock

from apps.dummy.task.dummytask import DummyTaskBuilder
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.node import OptNode
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import result_types
from golem.task.taskcomputer import DockerTaskThread
from golem.task.taskserver import TaskServer
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from .test_docker_image import DockerTestCase

# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


# TODO: extract code common to this class,
# TestDockerBlenderTask and TestDockerLuxrenderTask to a superclass

@ci_skip
class TestDockerDummyTask(TempDirFixture, DockerTestCase):
    TASK_FILE = "docker-dummy-test-task.json"

    def setUp(self):
        TempDirFixture.setUp(self)
        DockerTestCase.setUp(self)
        self.error_msg = None
        self.dirs_to_remove = []
        self.files_to_remove = []
        self.node = None
        self._send_task_failed = TaskServer.send_task_failed

    def tearDown(self):
        if self.node and self.node.client:
            self.node.client.quit()
        for f in self.files_to_remove:
            if path.isfile(f):
                remove(f)
        for dir_ in self.dirs_to_remove:
            if path.isdir(dir_):
                shutil.rmtree(dir_)
        TaskServer.send_task_failed = self._send_task_failed

        DockerTestCase.tearDown(self)
        TempDirFixture.tearDown(self)

    def _test_task_definition(self):
        task_file = path.join(path.dirname(__file__), self.TASK_FILE)
        with open(task_file, "r") as f:
            task_def = json.decode(f.read())

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        golem_dir = get_golem_path()

        def set_root_dir(p):
            return p.replace("$GOLEM_DIR", golem_dir)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        # task_def.output_file = set_root_dir(task_def.output_file)
        return task_def

    def _test_task(self):

        task_def = self._test_task_definition()
        node_name = "0123456789abcdef"
        dir_manager = DirManager(self.path)
        task_builder = DummyTaskBuilder(node_name=node_name,
                                        task_definition=task_def,
                                        root_path=self.tempdir,
                                        dir_manager=dir_manager)
        dummy_task = task_builder.build()
        return dummy_task

    def _run_docker_task(self, dummy_task, timeout=60 * 5):
        task_id = dummy_task.header.task_id
        extra_data = dummy_task.query_extra_data(1.0)
        ctd = extra_data.ctd
        ctd.deadline = timeout_to_deadline(timeout)

        # Create the computing node
        self.node = OptNode(datadir=self.path, use_docker_machine_manager=False)
        self.node.client.start = Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()
        # ccd.estimated_blender_performance = 2000.0
        # ccd.estimated_lux_performance = 2000.0

        task_server = TaskServer(Mock(), ccd, Mock(), self.node.client,
                                 use_docker_machine_manager=False)
        task_computer = task_server.task_computer

        resource_dir = task_computer.resource_manager.get_resource_dir(task_id)
        temp_dir = task_computer.resource_manager.get_temporary_dir(task_id)
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources
        common_prefix = path.commonprefix(dummy_task.task_definition.resources)
        common_prefix = path.dirname(common_prefix)

        for res_file in dummy_task.task_definition.resources:
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
        task_computer.task_given(ctd)
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

    def test_dummytask_test(self):
        task = self._test_task()
        task.max_pending_client_results = 5
        computer = TaskTester(task, self.tempdir, Mock(), Mock())
        computer.run()
        computer.tt.join(60.0)

        # here is the result file
        dirname = os.path.dirname(computer.tt.result[0]['data'][0])
        # TODO finish the test when luxrender tests are merged

    def test_dummytask_subtask(self):
        task = self._test_task()
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsNone(error_msg)

        # Check the number and type of result files:
        result = task_thread.result
        self.assertEqual(result["result_type"], result_types["files"])
        self.assertGreaterEqual(len(result["data"]), 3)
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDOUT_FILE
                for f in result["data"]))
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDERR_FILE
                for f in result["data"]))
        self.assertTrue(
            any("output" in f for f in result["data"]))
