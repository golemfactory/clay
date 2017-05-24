import os
import shutil
import unittest
import zipfile
import zlib
from copy import copy

from mock import MagicMock


from golem.core.common import is_linux
from golem.core.fileshelper import outer_dir_path
from golem.core.simpleserializer import CBORSerializer
from golem.resource.dirmanager import DirManager
from golem.resource.resource import TaskResourceHeader
from golem.resource.resourcesmanager import DistributedResourceManager
from golem.task.taskbase import result_types, TaskEventListener
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from apps.core.task.coretask import (CoreTask, logger, log_key_error, TaskTypeInfo,
                                     CoreTaskBuilder, AcceptClientVerdict)
from apps.core.task.coretaskstate import TaskDefinition


class TestCoreTask(LogTestCase, TestDirFixture):
    def _get_core_task(self):
        task_definition = TaskDefinition()
        task_definition.max_price = 100
        task_definition.task_id = "xyz"
        task_definition.estimated_memory = 1024
        task_definition.full_task_timeout = 3000
        task_definition.subtask_timeout = 30
        task = CoreTask(
            src_code="src code",
            task_definition=task_definition,
            node_name="ABC",
            owner_address="10.10.10.10",
            owner_port=123,
            owner_key_id="key",
            environment="environment",
            resource_size=1024,
        )
        dm = DirManager(self.path)
        task.initialize(dm)
        return task

    def test_core_task(self):
        task = self._get_core_task()
        self.assertEqual(task.header.max_price, 100)

        subtask_id = "xxyyzz"

        task.subtasks_given[subtask_id] = {}
        self.assertEqual(task.get_stdout(subtask_id), "")
        self.assertEqual(task.get_stderr(subtask_id), "")
        self.assertEqual(task.get_results(subtask_id), [])

        task.stdout[subtask_id] = "stdout in string"
        task.stderr[subtask_id] = "stderr in string"
        task.results[subtask_id] = range(10)

        self.assertEqual(task.get_stdout(subtask_id), task.stdout[subtask_id])
        self.assertEqual(task.get_stderr(subtask_id), task.stderr[subtask_id])
        self.assertEqual(task.get_results(subtask_id), range(10))

        files = self.additional_dir_content([2])
        with open(files[0], 'w') as f:
            f.write("stdout in file")
        with open(files[1], 'w') as f:
            f.write("stderr in file")

        task.stdout[subtask_id] = files[0]
        task.stderr[subtask_id] = files[1]

        self.assertEqual(task.get_stdout(subtask_id), files[0])
        self.assertEqual(task.get_stderr(subtask_id), files[1])
        
        self.assertEqual(task.after_test(None, None), {})

        assert len(task.listeners) == 0

        class TestListener(TaskEventListener):
            def __init__(self):
                super(TestListener, self).__init__()
                self.notify_called = False
                self.task_id = None

            def notify_update_task(self, task_id):
                self.notify_called = True
                self.task_id = task_id

        l1 = TestListener()
        l2 = TestListener()
        l3 = TestListener()
        task.register_listener(l1)
        task.register_listener(l2)
        task.register_listener(l3)
        task.unregister_listener(l2)
        task.notify_update_task()
        assert not l2.notify_called
        assert l1.notify_called
        assert l3.notify_called
        assert l1.task_id == "xyz"
        assert l3.task_id == "xyz"
        assert l2.task_id is None

    def test_interpret_task_results_without_sorting(self):
        task = self._get_core_task()

        subtask_id = "xxyyzz"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"

        files_copy = copy(files)

        task.interpret_task_results(subtask_id, files, result_types["files"], False)

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in files_copy:
            with open(f, 'w'):
                pass

        task.interpret_task_results(subtask_id, files_copy, result_types["files"], False)
        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        for f in files_copy:
            with open(f, 'w'):
                pass
        os.remove(files[0])
        os.makedirs(files[0])
        with self.assertLogs(logger, level="WARNING"):
            task.interpret_task_results(subtask_id, files_copy, result_types["files"], False)
        assert task.results[subtask_id] == [files[1], files[4]]

        os.removedirs(files[0])

        for f in files + files_copy:
            if os.path.isfile(f):
                os.remove(f)
            assert not os.path.isfile(f)

        subtask_id = "aabbcc"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"

        res = [self.__compress_and_dump_file(files[0], "abc"*1000),
               self.__compress_and_dump_file(files[1], "def"*100),
               self.__compress_and_dump_file(files[2], "outputlog"),
               self.__compress_and_dump_file(files[3], "errlog"),
               self.__compress_and_dump_file(files[4], "ghi")]

        task.interpret_task_results(subtask_id, res, result_types["data"], False)

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in [files[0], files[1], files[4]]:
            self.assertTrue(os.path.isfile(os.path.join(task.tmp_dir, os.path.basename(f))))

        for f in [files[2], files[3]]:
            self.assertTrue(os.path.isfile(os.path.join(task.tmp_dir, subtask_id,
                                                        os.path.basename(f))))

        subtask_id = "112233"
        task.interpret_task_results(subtask_id, res, 58, False)
        self.assertEqual(task.results[subtask_id], [])
        self.assertEqual(task.stderr[subtask_id], "[GOLEM] Task result 58 not supported")
        self.assertEqual(task.stdout[subtask_id], "")

    def test_interpret_task_results_with_sorting(self):
        """ Test results sorting in interpret method"""
        task = self._get_core_task()

        subtask_id = "xxyyzz"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2]+".log")
        files[2] += ".log"
        shutil.move(files[3], files[3]+"err.log")
        files[3] += "err.log"

        task.interpret_task_results(subtask_id, files, result_types["files"])

        sorted_files = sorted([files[0], files[1], files[4]])

        sorted_files[0] = outer_dir_path(sorted_files[0])
        sorted_files[1] = outer_dir_path(sorted_files[1])
        sorted_files[2] = outer_dir_path(sorted_files[2])

        assert task.results[subtask_id] == [sorted_files[0], sorted_files[1], sorted_files[2]]
        assert task.stderr[subtask_id] == files[3]
        assert task.stdout[subtask_id] == files[2]

    def test_restart(self):
        task = self._get_core_task()
        task.num_tasks_received = 1
        task.last_task = 8
        task.num_failed_subtasks = 2
        task.counting_nodes = MagicMock()

        task.subtasks_given["xyz"] = {'status': SubtaskStatus.finished,
                                      'start_task': 1,
                                      'end_task': 1,
                                      'node_id': 'ABC'}
        task.subtasks_given["abc"] = {'status': SubtaskStatus.failure,
                                      'start_task': 4,
                                      'end_task': 4,
                                      'node_id': 'abc'}
        task.subtasks_given["def"] = {'status': SubtaskStatus.starting,
                                      'start_task': 8,
                                      'end_task': 8,
                                      'node_id': 'DEF'}
        task.subtasks_given["ghi"] = {'status': SubtaskStatus.resent,
                                      'start_task': 2,
                                      'end_task': 2,
                                      'node_id': 'aha'}
        task.subtasks_given["jkl"] = {'status': SubtaskStatus.downloading,
                                      'start_task': 8,
                                      'end_task': 8,
                                      'node_id': 'DEF'}
        task.restart()
        assert task.num_tasks_received == 0
        assert task.last_task == 8
        assert task.num_failed_subtasks == 5
        assert task.subtasks_given["xyz"]["status"] == SubtaskStatus.restarted
        assert task.subtasks_given["abc"]["status"] == SubtaskStatus.failure
        assert task.subtasks_given["def"]["status"] == SubtaskStatus.restarted
        assert task.subtasks_given["ghi"]["status"] == SubtaskStatus.resent
        assert task.subtasks_given["jkl"]["status"] == SubtaskStatus.restarted

    @staticmethod
    def __compress_and_dump_file(file_name, data):
        file_data = zlib.compress(data, 9)
        return CBORSerializer.dumps((os.path.basename(file_name), file_data))

    def test_interpret_log(self):
        task = self._get_core_task()
        # None as a log name
        assert task._interpret_log(None) == ""
        # log that is not a file
        assert task._interpret_log("NOT A FILE") == "NOT A FILE"
        # access to log without problems
        files = self.additional_dir_content([2])
        with open(files[0], 'w') as f:
            f.write("Some information from log")
        assert task._interpret_log(files[0]) == "Some information from log"
        # no access to the file
        if is_linux():

            with open(files[1], 'w') as f:
                f.write("No access to this information")
            os.chmod(files[1], 0o200)

            with self.assertLogs(logger, level="WARNING"):
                task._interpret_log(files[1])

            os.chmod(files[1], 0o700)

    def test_needs_computation(self):
        c = self._get_core_task()
        c.total_tasks = 13
        assert c.needs_computation()
        c.last_task = 4
        assert c.needs_computation()
        c.last_task = 13
        assert not c.needs_computation()
        c.num_failed_subtasks = 5
        assert c.needs_computation()
        c.num_failed_subtasks = 0
        assert not c.needs_computation()

    def test_get_active_tasks(self):
        c = self._get_core_task()
        assert c.get_active_tasks() == 0
        c.last_task = 5
        assert c.get_active_tasks() == 5
        c.last_task = 27
        assert c.get_active_tasks() == 27

    def test_get_tasks_left(self):
        c = self._get_core_task()
        c.total_tasks = 13
        assert c.get_tasks_left() == 13
        c.last_task = 3
        assert c.get_tasks_left() == 10
        c.num_failed_subtasks = 2
        assert c.get_tasks_left() == 12
        c.num_failed_subtasks = 3
        assert c.get_tasks_left() == 13
        c.last_task = 13
        assert c.get_tasks_left() == 3
        c.num_failed_subtasks = 0
        assert c.get_tasks_left() == 0

    def test_abort(self):
        c = self._get_core_task()
        c.abort()

    def test_get_progress(self):
        c = self._get_core_task()
        assert c.get_progress() == 0
        c.total_tasks = 13
        assert c.get_progress() == 0
        c.num_tasks_received = 1
        assert abs(c.get_progress() - 0.0769) < 0.01
        c.num_tasks_received = 7
        assert abs(c.get_progress() - 0.538) < 0.01
        c.num_tasks_received = 13
        assert c.get_progress() == 1

    def test_update_task_state(self):
        c = self._get_core_task()
        c.update_task_state("subtask1")

    def test_get_trust_mod(self):
        c = self._get_core_task()
        assert c.get_trust_mod("subtask1") == 1.0

    def test_add_resources(self):
        c = self._get_core_task()
        c.add_resources(["file1", "file2"])
        assert c.res_files == ["file1", "file2"]

    def test_query_extra_data_for_test_task(self):
        c = self._get_core_task()
        assert c.query_extra_data_for_test_task() is None

    def test_get_resources(self):
        c = self._get_core_task()
        th = TaskResourceHeader(self.path)
        assert c.get_resources(th) is None

        files = self.additional_dir_content([[1], [[1], [2, [3]]]])
        c.task_resources = files[1:]
        resource = c.get_resources(th)
        assert os.path.isfile(resource)
        assert zipfile.is_zipfile(resource)
        z = zipfile.ZipFile(resource)
        in_z = z.namelist()
        assert len(in_z) == 6

        assert c.get_resources(th, 2) == files[1:]

        th2, p = c.get_resources(th, 1)
        assert p == []
        assert th2.files_data == []
        assert th2.sub_dir_headers == []

        with open(files[0], 'w') as f:
            f.write("ABCD")

        drm = DistributedResourceManager(os.path.dirname(files[0]))
        res_files = drm.split_file(files[0])
        c.add_resources({files[0]: res_files})
        th2, p = c.get_resources(th, 1)
        assert len(p) == 1
        assert len(th2.files_data) == 1
        assert th2.sub_dir_headers == []

        assert c.get_resources(th, 3) is None

    def test_result_incoming(self):
        c = self._get_core_task()
        assert c._accept_client("Node 1") == AcceptClientVerdict.ACCEPTED
        c.subtasks_given["subtask1"] = {"node_id": "Node 1"}
        assert c.counting_nodes["Node 1"]._finishing == 0
        c.result_incoming("subtask1")
        assert c.counting_nodes["Node 1"]._finishing == 1
        assert c._accept_client("Node 1") == AcceptClientVerdict.SHOULD_WAIT
        c._mark_subtask_failed("subtask1")
        assert c._accept_client("Node 1") == AcceptClientVerdict.REJECTED

    def test_create_path_in_load_task_result(self):
        c = self._get_core_task()
        assert not os.path.isdir(os.path.join(c.tmp_dir, "subtask1"))
        c.load_task_results(MagicMock(), result_types['data'], "subtask1")
        assert os.path.isdir(os.path.join(c.tmp_dir, "subtask1"))


class TestLogKeyError(LogTestCase):
    def test_log_key_error(self):
        with self.assertLogs(logger, level="WARNING") as l:
            assert not log_key_error("arg1", 131, "arg31380", [], arg="31", kwarg=231)
        assert "131" in l.output[0]


class TestTaskTypeInfo(unittest.TestCase):
    def test_init(self):
        tti = TaskTypeInfo("Name1", "Definition1", "Defaults", "Options", "builder")
        assert tti.name == "Name1"
        assert tti.defaults == "Defaults"
        assert tti.options == "Options"
        assert tti.task_builder_type == "builder"
        assert tti.definition == "Definition1"
        assert tti.dialog is None
        assert tti.dialog_controller is None
        assert tti.output_formats == []
        assert tti.output_file_ext == []

        tti = TaskTypeInfo("Name2", "Definition2", "Defaults2", "Options2", "builder2", "dialog",
                           "controller")
        assert tti.name == "Name2"
        assert tti.defaults == "Defaults2"
        assert tti.options == "Options2"
        assert tti.task_builder_type == "builder2"
        assert tti.definition == "Definition2"
        assert tti.dialog == "dialog"
        assert tti.dialog_controller == "controller"
        assert tti.output_formats == []
        assert tti.output_file_ext == []

    def test_preview_methods(self):
        assert TaskTypeInfo.get_task_num_from_pixels(0, 0, None, 10) == 0
        assert TaskTypeInfo.get_task_border("subtask1", None, 10) == []


class TestCoreTaskBuilder(unittest.TestCase):

    def _get_core_task_builder(self):
        return CoreTaskBuilder("Node1", MagicMock(), "path", "manager")

    def test_init(self):
        builder = self._get_core_task_builder()
        assert builder.TASK_CLASS == CoreTaskBuilder.TASK_CLASS
        assert builder.TASK_CLASS == CoreTask
        assert builder.task_definition is not None
        assert builder.node_name == "Node1"
        assert builder.root_path == "path"
        assert builder.dir_manager == "manager"

    def test_get_task_kwargs(self):
        builder = self._get_core_task_builder()

        class C(object):
            pass

        c = C()
        kwargs = builder.get_task_kwargs(arg1="arg1", arg2=1380, arg3=c)
        assert kwargs["arg1"] == "arg1"
        assert kwargs["arg2"] == 1380
        assert kwargs["arg3"] == c
        assert kwargs["node_name"] == "Node1"
        assert kwargs["src_code"] == ""
        assert kwargs["environment"] is None
        assert isinstance(kwargs["task_definition"], MagicMock)

    def test_build(self):
        builder = self._get_core_task_builder()
        assert isinstance(builder.build(), CoreTask)
