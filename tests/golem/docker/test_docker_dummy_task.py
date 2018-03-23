import json
import logging
import os
from os import makedirs, path, remove
import shutil
from unittest import mock
from unittest.mock import Mock

from apps.dummy.task.dummytask import DummyTaskBuilder, DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.fileshelper import find_file_with_ext
from golem.core.simpleserializer import DictSerializer
from golem.node import Node
from golem.resource.dirmanager import DirManager, symlink_or_copy, \
    rmlink_or_rmtree
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ResultType
from golem.task.taskcomputer import DockerTaskThread
from golem.task.taskserver import TaskServer
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from .test_docker_image import DockerTestCase

# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


# TODO: extract code common to this class and TestDockerBlenderTask
# to a superclass. issue: G #2393

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data_dir = os.path.join(get_golem_path(),
                                "apps",
                                "dummy",
                                "test_data")
        code_dir = os.path.join(get_golem_path(),
                                "apps",
                                "dummy",
                                "resources",
                                "code_dir")
        cls.test_tmp = os.path.join(get_golem_path(),
                                    "apps",
                                    "dummy",
                                    "test_tmp")
        os.mkdir(cls.test_tmp)

        cls.code_link = os.path.join(cls.test_tmp, "code")
        cls.data_link = os.path.join(cls.test_tmp, "data")

        symlink_or_copy(code_dir, cls.code_link)
        symlink_or_copy(data_dir, cls.data_link)

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

    @classmethod
    def tearDownClass(cls):
        rmlink_or_rmtree(cls.code_link)
        rmlink_or_rmtree(cls.data_link)
        os.rmdir(cls.test_tmp)

    def _test_task_definition(self) -> DummyTaskDefinition:
        task_file = path.join(path.dirname(__file__), self.TASK_FILE)
        with open(task_file, "r") as f:
            task_def = DictSerializer.load(json.loads(f.read()))  # type: DummyTaskDefinition

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        golem_dir = get_golem_path()

        def set_root_dir(p):
            return p.replace("$GOLEM_DIR", golem_dir)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        task_def.shared_data_files = [set_root_dir(x)
                                      for x in task_def.shared_data_files]
        task_def.code_dir = set_root_dir(task_def.code_dir)

        return task_def

    def _test_task(self) -> DummyTask:
        DummyTask.VERIFICATION_QUEUE._reset()
        task_def = self._test_task_definition()
        node_name = "0123456789abcdef"
        dir_manager = DirManager(self.path)
        task_builder = DummyTaskBuilder(node_name, task_def, self.tempdir,
                                        dir_manager)
        task = task_builder.build()  # type: DummyTask
        task.max_pending_client_results = 5
        return task

    def _run_docker_task(self, task: DummyTask, timeout=60 * 5):
        task_id = task.header.task_id
        extra_data = task.query_extra_data(1.0)
        ctd = extra_data.ctd
        ctd['deadline'] = timeout_to_deadline(timeout)

        # Create the computing node
        self.node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=ClientConfigDescriptor(),
            use_docker_manager=False,
        )
        with mock.patch('golem.client.EthereumTransactionSystem'):
            self.node.client = self.node._client_factory(Mock())
        self.node.client.start = Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()

        with mock.patch(
                "golem.network.concent.handlers_library"
                ".HandlersLibrary"
                ".register_handler"):
            task_server = TaskServer(
                node=Mock(),
                config_desc=ccd,
                client=self.node.client,
                use_docker_manager=False
            )
        task_server.task_keeper.task_headers[task_id] = task.header
        task_computer = task_server.task_computer

        resource_dir = task_computer.resource_manager.get_resource_dir(task_id)
        temp_dir = task_computer.resource_manager.get_temporary_dir(task_id)
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources - data
        td = task.task_definition
        if len(td.shared_data_files) > 1:
            common_data_prefix = path.commonprefix(td.shared_data_files)
            common_data_prefix = path.dirname(common_data_prefix)
        else:
            common_data_prefix = path.dirname(
                next(iter(td.shared_data_files)))  # first elem of set

        for res_file in td.shared_data_files:
            dest_file = path.join(resource_dir,
                                  "data",
                                  res_file[len(common_data_prefix) + 1:])
            dest_dirname = path.dirname(dest_file)
            if not path.exists(dest_dirname):
                makedirs(dest_dirname)
            shutil.copyfile(res_file, dest_file)

        for res_file in td.code_files:
            dest_file = path.join(resource_dir,
                                  "code",
                                  res_file)
            dest_dirname = path.dirname(dest_file)
            if not path.exists(dest_dirname):
                makedirs(dest_dirname)
            shutil.copyfile(os.path.join(td.code_dir, res_file), dest_file)

        def send_task_failed(_, __, ___, error_msg):
            self.error_msg = error_msg

        TaskServer.send_task_failed = send_task_failed

        # Start task computation
        task_computer.task_given(ctd)
        result = task_computer.resource_given(ctd['task_id'])
        self.assertTrue(result)

        # Thread for task computation should be created by now
        with task_computer.lock:
            task_thread = task_computer.counting_thread

        if task_thread:
            task_thread.join(60.0)

        return task_thread, self.error_msg, temp_dir

    def _change_file_location(self, filepath, newfilepath):
        if os.path.exists(newfilepath):
            os.remove(newfilepath)

        new_file_dir = os.path.dirname(newfilepath)
        if not os.path.exists(new_file_dir):
            os.makedirs(new_file_dir)

        shutil.copy(filepath, newfilepath)
        return newfilepath

    def _extract_results(self, computer: LocalComputer, task: DummyTask,
                         subtask_id):
        """
        Since the local computer uses temp dir, you should copy files out of
        there before you use local computer again.
        Otherwise the files would get overwritten (during the verification
        process).
        This is a problem only in test suite. In real life provider and
        requestor are separate machines
        :param computer:
        :param task:
        :return:
        """
        dirname = os.path.dirname(computer.tt.result['data'][0])

        result = find_file_with_ext(dirname, [".result"])

        self.assertTrue(path.isfile(result))

        ## copy to new location
        new_file_dir = path.join(path.dirname(result), subtask_id)

        new_result = self._change_file_location(result,
                                                path.join(new_file_dir,
                                                          "new.result"))

        return new_result

    @mock.patch('apps.core.task.verifier.deadline_to_timeout')
    def test_dummy_real_task(self, mock_dtt):
        mock_dtt.return_value = 1.0

        task = self._test_task()
        ctd = task.query_extra_data(1.0).ctd

        print(ctd)
        print(type(ctd))

        computer = LocalComputer(
            root_path=self.tempdir,
            success_callback=Mock(),
            error_callback=Mock(),
            compute_task_def=ctd,
            resources=task.task_resources,
        )

        computer.run()
        computer.tt.join()

        output = self._extract_results(computer, task, ctd['subtask_id'])

        task.create_reference_data_for_task_validation()

        ## assert good results - should pass
        self.assertEqual(task.num_tasks_received, 0)
        task.computation_finished(ctd['subtask_id'], [output],
                                  result_type=ResultType.FILES,
                                  verification_finished_=lambda: None)

        is_subtask_verified = task.verify_subtask(ctd['subtask_id'])
        self.assertTrue(is_subtask_verified)
        self.assertEqual(task.num_tasks_received, 1)

        ## assert bad results - should fail
        bad_output = path.join(path.dirname(output), "badfile.result")
        ctd = task.query_extra_data(10000.).ctd
        task.computation_finished(ctd['subtask_id'], [bad_output],
                                  result_type=ResultType.FILES,
                                  verification_finished_=lambda: None)

        self.assertFalse(task.verify_subtask(ctd['subtask_id']))
        self.assertEqual(task.num_tasks_received, 1)

    def test_dummytask_TaskTester_should_pass(self):
        task = self._test_task()

        computer = TaskTester(task, self.tempdir, Mock(), Mock())
        computer.run()
        computer.tt.join(60.0)

        dirname = os.path.dirname(computer.tt.result[0]['data'][0])
        result = find_file_with_ext(dirname, [".result"])

        assert path.isfile(result)

    def test_dummy_subtask(self):
        task = self._test_task()
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsNone(error_msg)

        # Check the number and type of result files:
        result = task_thread.result
        self.assertEqual(result["result_type"], ResultType.FILES)
        self.assertGreaterEqual(len(result["data"]), 3)
        self.assertTrue(any(path.basename(f) == DockerTaskThread.STDOUT_FILE
                            for f in result["data"]))
        self.assertTrue(any(path.basename(f) == DockerTaskThread.STDERR_FILE
                            for f in result["data"]))
        self.assertTrue(any(f.endswith(DummyTask.RESULT_EXT) and "out" in f
                            for f in result["data"]))
