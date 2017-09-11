import logging
import os
import shutil
from os import makedirs, path, remove

import jsonpickle as json
from mock import Mock

from apps.mlpoc.task.mlpoctask import MLPOCTaskBuilder, MLPOCTask
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefinition
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.fileshelper import find_file_with_ext
from golem.node import OptNode
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
# to a superclass

@ci_skip
class TestDockerMLPOCTask(TempDirFixture, DockerTestCase):
    TASK_FILE = "docker-mlpoc-test-task.json"

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
        data_dir = os.path.join(get_golem_path(),
                                "apps",
                                "mlpoc",
                                "test_data")
        code_dir = os.path.join(get_golem_path(),
                                "apps",
                                "mlpoc",
                                "resources",
                                "code_pytorch")
        cls.test_tmp = os.path.join(get_golem_path(),
                                    "apps",
                                    "mlpoc",
                                    "test_tmp")
        os.mkdir(cls.test_tmp)

        assert os.path.isdir(cls.test_tmp)

        cls.code_link = os.path.join(cls.test_tmp, "code")
        cls.data_link = os.path.join(cls.test_tmp, "data")

        shutil.copytree(code_dir, cls.code_link)  # copying instead of linking, because otherwise some some files are messed up
        shutil.copytree(data_dir, cls.data_link)  # copying instead of linking, because otherwise some some files are messed up
        assert cls.code_link
        assert cls.data_link

        # use mock black box from test_code
        mock_bb_src = os.path.join(get_golem_path(),
                                   "apps",
                                   "mlpoc",
                                   "test_code",
                                   "mock_box_callback.py")
        mock_bb_dst = os.path.join(cls.code_link, "impl", "box_callback.py")
        os.remove(mock_bb_dst)
        shutil.copy(mock_bb_src, mock_bb_dst)  # copying instead of linking, because otherwise some some files are messed up

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

    def _test_task_definition(self) -> MLPOCTaskDefinition:
        task_file = path.join(path.dirname(__file__), self.TASK_FILE)
        with open(task_file, "r") as f:
            task_def = json.decode(f.read())  # type: MLPOCTaskDefinition

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        # and $TMP_DIR by self.tmp_path
        golem_dir = get_golem_path()

        def set_root_dir(p):
            return p.replace("$GOLEM_DIR", golem_dir) \
                .replace("$TMP_DIR", self.test_tmp)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        task_def.shared_data_files = [set_root_dir(x)
                                      for x in task_def.shared_data_files]
        task_def.code_dir = set_root_dir(task_def.code_dir)

        return task_def

    def _test_task(self) -> MLPOCTask:
        task_def = self._test_task_definition()
        node_name = "0123456789abcdef"
        dir_manager = DirManager(self.path)
        task_builder = MLPOCTaskBuilder(node_name, task_def, self.tempdir,
                                        dir_manager)
        task = task_builder.build()  # type: MLPOCTask
        task.max_pending_client_results = 5
        return task

    def _run_docker_task(self, task: MLPOCTask, timeout=60*5):
        task_id = task.header.task_id
        extra_data = task.query_extra_data(1.0)
        ctd = extra_data.ctd
        ctd.deadline = timeout_to_deadline(timeout)

        # Create the computing node
        self.node = OptNode(datadir=self.path, use_docker_machine_manager=False)
        self.node.client.start = Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()

        task_server = TaskServer(Mock(), ccd, Mock(), self.node.client,
                                 use_docker_machine_manager=False)
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
            # first elem of set
            common_data_prefix = path.dirname(next(iter(td.shared_data_files)))

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
            task_thread.join(180.0)

        return task_thread, self.error_msg, temp_dir

    def _change_file_location(self, filepath, newfilepath):
        if os.path.exists(newfilepath):
            os.remove(newfilepath)

        new_file_dir = os.path.dirname(newfilepath)
        if not os.path.exists(new_file_dir):
            os.makedirs(new_file_dir)

        shutil.copy(filepath, newfilepath)
        return newfilepath

    def _extract_results(self,
                         computer: LocalComputer,
                         task: MLPOCTask,
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
        new_file_path = path.join(path.dirname(result), subtask_id, "a.result")

        new_result = self._change_file_location(result, new_file_path)

        return new_result

    # def test_mlpoc_real_task(self):
    #
    #     task = self._test_task()
    #     ctd = task.query_extra_data(1.0).ctd
    #
    #     computer = LocalComputer(
    #         task,
    #         self.tempdir,
    #         Mock(),
    #         Mock(),
    #         lambda: ctd
    #     )
    #
    #     computer.run()
    #     computer.tt.join()
    #
    #     output = self._extract_results(computer, task, ctd.subtask_id)
    #
    #     task.create_reference_data_for_task_validation()
    #
    #     ## assert good results - should pass
    #     self.assertEqual(task.num_tasks_received, 0)
    #     task.computation_finished(ctd.subtask_id, [output],
    #                               result_type=ResultType.FILES)
    #
    #     is_subtask_verified = task.verify_subtask(ctd.subtask_id)
    #     self.assertTrue(is_subtask_verified)
    #     self.assertEqual(task.num_tasks_received, 1)
    #
    #     ## assert bad results - should fail
    #     bad_output = path.join(path.dirname(output), "badfile.result")
    #     ctd = task.query_extra_data(10000.).ctd
    #     task.computation_finished(ctd.subtask_id, [bad_output],
    #                               result_type=ResultType.FILES)
    #
    #     self.assertFalse(task.verify_subtask(ctd.subtask_id))
    #     self.assertEqual(task.num_tasks_received, 1)

    def test_mlpoctask_TaskTester_should_pass(self):
        task = self._test_task()

        computer = TaskTester(task, self.tempdir, Mock(), Mock())
        computer.run()
        computer.tt.join(180.0)

        output_dir = os.path.commonpath(computer.tt.result[0]['data'])

        results = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if "stderr" not in f and "stdout" not in f]

        assert len(results) == task.task_definition.options.number_of_epochs
        for epoch_dir in results:
            assert len([f for f in os.listdir(epoch_dir) if f.endswith(".end")]) == 1
            assert len([f for f in os.listdir(epoch_dir) if f.endswith(".begin")]) == 1
            assert len(os.listdir(epoch_dir)) == 2

    def test_mlpoc_subtask(self):
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

        self.assertEqual(len([0 for f in result["data"] if f.endswith(".end")]),
                        task.task_definition.options.number_of_epochs)
        self.assertEqual(len([0 for f in result["data"] if f.endswith(".begin")]),
                         task.task_definition.options.number_of_epochs)