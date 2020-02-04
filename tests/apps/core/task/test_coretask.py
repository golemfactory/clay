import os
import shutil
from copy import copy
from tempfile import TemporaryDirectory
from typing import Optional
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from freezegun import freeze_time
from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from apps.core.task.coretask import (
    CoreTask, logger, log_key_error,
    CoreTaskTypeInfo, CoreTaskBuilder, AcceptClientVerdict)
from apps.core.task.coretaskstate import TaskDefinition
from golem.core.common import is_linux
from golem.core.fileshelper import outer_dir_path
from golem.environments import environment
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import TaskEventListener, TaskResult
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


def env_with_file(_self):
    env = environment.Environment()
    return env


class TestCoreTask(LogTestCase, TestDirFixture):

    # CoreTask is abstract, so in order to be able to instantiate it
    # we have to override some stuff
    class CoreTaskDeabstracted(CoreTask):
        ENVIRONMENT_CLASS = env_with_file  # type: ignore
        EXTRA_DATA = CoreTask.ExtraData(sth="sth")

        def query_extra_data(self, *args, **kwargs):
            return self.EXTRA_DATA

        def query_extra_data_for_test_task(self):
            pass

    @staticmethod
    def _get_core_task_definition(subtasks_count=1):
        task_definition = TaskDefinition()
        task_definition.max_price = 100
        task_definition.task_id = "deadbeef"
        task_definition.estimated_memory = 1024
        task_definition.timeout = 3000
        task_definition.subtask_timeout = 30
        task_definition.subtasks_count = subtasks_count
        return task_definition

    def test_instantiation(self):
        task_def = self._get_core_task_definition()
        node = dt_p2p_factory.Node()

        # abstract class cannot be instantiated
        # pylint: disable=abstract-class-instantiated
        with self.assertRaises(TypeError):
            CoreTask(task_def, owner=dt_p2p_factory.Node())

        class CoreTaskDeabstacted(CoreTask):

            def query_extra_data(self, *args, **kwargs):
                pass

        # ENVIRONMENT has to be set
        with self.assertRaises(TypeError):
            CoreTaskDeabstacted(task_def, node)

        class CoreTaskDeabstractedEnv(CoreTask):
            ENVIRONMENT_CLASS = env_with_file

            def query_extra_data(self, *args, **kwargs):
                pass

            def query_extra_data_for_test_task(self):
                pass

        task = CoreTaskDeabstractedEnv(task_def, node)
        self.assertIsInstance(task, CoreTask)

    def _get_core_task(self, *, subtasks_count=1):
        task_def = TestCoreTask._get_core_task_definition(subtasks_count)
        task = self.CoreTaskDeabstracted(
            task_definition=task_def,
            owner=dt_p2p_factory.Node(),
            resource_size=1024
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
        task.results[subtask_id] = list(range(10))

        self.assertEqual(task.get_stdout(subtask_id), task.stdout[subtask_id])
        self.assertEqual(task.get_stderr(subtask_id), task.stderr[subtask_id])
        self.assertEqual(task.get_results(subtask_id), list(range(10)))

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
        assert l1.task_id == "deadbeef"
        assert l3.task_id == "deadbeef"
        assert l2.task_id is None

    def test_create_task_id(self):
        # when
        task_id = CoreTask.create_task_id(b'\xbe\xef\xde\xad\xbe\xef')

        # then
        self.assertRegex(task_id, "^[-0-9a-f]{23}-beefdeadbeef$")

    def test_create_subtask_id(self):
        # given
        t = self._get_core_task()
        t.header.task_id = CoreTask.create_task_id(b'\xbe\xef\xde\xad\xbe\xef')

        # when
        subtask_id = t.create_subtask_id()

        # then
        self.assertRegex(subtask_id, "^[-0-9a-f]{23}-beefdeadbeef$")

    def test_interpret_task_results_without_sorting(self):
        task = self._get_core_task()

        subtask_id = "xxyyzz"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2] + ".log")
        files[2] += ".log"
        shutil.move(files[3], files[3] + "err.log")
        files[3] += "err.log"

        files_copy = copy(files)

        task.interpret_task_results(subtask_id, TaskResult(files=files), False)

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [
                         files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in files_copy:
            with open(f, 'w'):
                pass

        task.interpret_task_results(
            subtask_id, TaskResult(files=files_copy), False)
        self.assertEqual(task.results[subtask_id], [
                         files[0], files[1], files[4]])
        for f in files_copy:
            with open(f, 'w'):
                pass
        os.remove(files[0])
        os.makedirs(files[0])
        with self.assertLogs(logger, level="WARNING"):
            task.interpret_task_results(
                subtask_id, TaskResult(files=files_copy), False)
        assert task.results[subtask_id] == [files[1], files[4]]

        os.removedirs(files[0])

        for f in files + files_copy:
            if os.path.isfile(f):
                os.remove(f)
            assert not os.path.isfile(f)

        subtask_id = "aabbcc"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2] + ".log")
        files[2] += ".log"
        shutil.move(files[3], files[3] + "err.log")
        files[3] += "err.log"

        self.__dump_file(files[0], "abc" * 1000)
        self.__dump_file(files[1], "def" * 100)
        self.__dump_file(files[2], "outputlog")
        self.__dump_file(files[3], "errlog")
        self.__dump_file(files[4], "ghi")
        res = files

        task.interpret_task_results(subtask_id, TaskResult(files=res), False)

        files[0] = outer_dir_path(files[0])
        files[1] = outer_dir_path(files[1])
        files[4] = outer_dir_path(files[4])

        self.assertEqual(task.results[subtask_id], [
                         files[0], files[1], files[4]])
        self.assertEqual(task.stderr[subtask_id], files[3])
        self.assertEqual(task.stdout[subtask_id], files[2])

        for f in [files[0], files[1], files[4]]:
            self.assertTrue(os.path.isfile(
                os.path.join(task.tmp_dir, os.path.basename(f))))

        for f in [files[2], files[3]]:
            self.assertTrue(os.path.isfile(os.path.join(task.tmp_dir, subtask_id,
                                                        os.path.basename(f))))

    def test_interpret_task_results_with_sorting(self):
        """ Test results sorting in interpret method"""
        task = self._get_core_task()

        subtask_id = "xxyyzz"
        files_dir = os.path.join(task.tmp_dir, subtask_id)
        files = self.additional_dir_content([5], sub_dir=files_dir)

        shutil.move(files[2], files[2] + ".log")
        files[2] += ".log"
        shutil.move(files[3], files[3] + "err.log")
        files[3] += "err.log"

        task.interpret_task_results(subtask_id, TaskResult(files=files))

        sorted_files = sorted([files[0], files[1], files[4]])

        sorted_files[0] = outer_dir_path(sorted_files[0])
        sorted_files[1] = outer_dir_path(sorted_files[1])
        sorted_files[2] = outer_dir_path(sorted_files[2])

        assert task.results[subtask_id] == [
            sorted_files[0], sorted_files[1], sorted_files[2]]
        assert task.stderr[subtask_id] == files[3]
        assert task.stdout[subtask_id] == files[2]

    def test_restart(self):
        task = self._get_core_task()
        task.num_tasks_received = 1
        task.last_task = 8
        task.num_failed_subtasks = 2
        task.counting_nodes = MagicMock()

        task.subtasks_given["deadbeef"] = {'status': SubtaskStatus.finished,
                                      'start_task': 1,
                                      'node_id': 'ABC'}
        task.subtasks_given["abc"] = {'status': SubtaskStatus.failure,
                                      'start_task': 4,
                                      'node_id': 'abc'}
        task.subtasks_given["def"] = {'status': SubtaskStatus.starting,
                                      'start_task': 8,
                                      'node_id': 'DEF'}
        task.subtasks_given["ghi"] = {'status': SubtaskStatus.resent,
                                      'start_task': 2,
                                      'node_id': 'aha'}
        task.subtasks_given["jkl"] = {'status': SubtaskStatus.downloading,
                                      'start_task': 8,
                                      'node_id': 'DEF'}
        task.restart()
        assert task.num_tasks_received == 0
        assert task.last_task == 8
        assert task.num_failed_subtasks == 5
        assert task.subtasks_given["deadbeef"]["status"] == \
               SubtaskStatus.restarted
        assert task.subtasks_given["abc"]["status"] == SubtaskStatus.failure
        assert task.subtasks_given["def"]["status"] == SubtaskStatus.restarted
        assert task.subtasks_given["ghi"]["status"] == SubtaskStatus.resent
        assert task.subtasks_given["jkl"]["status"] == SubtaskStatus.restarted

    @staticmethod
    def __dump_file(file_name, data):
        with open(file_name, 'w') as f:
            f.write(data)

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
        c = self._get_core_task(subtasks_count=13)
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
        c = self._get_core_task(subtasks_count=13)
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
        c = self._get_core_task(subtasks_count=13)
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

    def test_result_incoming_rejected(self):
        c = self._get_core_task()
        assert c.accept_client("nod1", 'oh') == AcceptClientVerdict.ACCEPTED
        c.subtasks_given["subtask1"] = {"node_id": "nod1"}
        c.result_incoming("subtask1")
        assert c.accept_client("nod1", 'oh') == AcceptClientVerdict.SHOULD_WAIT
        c._mark_subtask_failed("subtask1")
        assert c.accept_client("nod1", 'oh') == AcceptClientVerdict.REJECTED

    def test_result_incoming_accepted(self):
        c = self._get_core_task()
        assert c.accept_client("nod1", 'oh') == AcceptClientVerdict.ACCEPTED
        c.subtasks_given["subtask1"] = {"node_id": "nod1"}
        c.result_incoming("subtask1")
        assert c.accept_client("nod1", 'oh') == AcceptClientVerdict.SHOULD_WAIT
        c.accept_results("subtask1", None)
        assert c.accept_client("nod1", 'oh') == AcceptClientVerdict.ACCEPTED

    def test_accept_results(self):
        c = self._get_core_task()

        c.subtasks_given["SUBTASK1"] = {}
        with self.assertRaises(Exception):
            c.accept_results("SUBTASK1", None)

        c.subtasks_given["SUBTASK1"] = {
            "status": SubtaskStatus.finished
        }
        with self.assertRaises(Exception):
            c.accept_results("SUBTASK1", None)

        c.subtasks_given["SUBTASK1"] = {
            "status": SubtaskStatus.finished
        }
        with self.assertRaises(Exception):
            c.accept_results("SUBTASK1", None)

        # this one should be ok
        c.subtasks_given["SUBTASK1"] = {
            "status": SubtaskStatus.downloading,
            "node_id": "NODE_ID",
        }
        c.accept_results("SUBTASK1", None)

    def test_new_compute_task_def(self):
        c = self._get_core_task()
        c.header.subtask_timeout = 1

        hash = "aaa"
        extra_data = Mock()
        perf_index = 0

        ctd = c._new_compute_task_def(
            hash, extra_data, perf_index)
        assert ctd['task_id'] == c.header.task_id
        assert ctd['subtask_id'] == hash
        assert ctd['extra_data'] == extra_data
        assert ctd['performance'] == perf_index
        assert ctd['docker_images'] == c.docker_images


class TestLogKeyError(LogTestCase):

    def test_log_key_error(self):
        with self.assertLogs(logger, level="WARNING") as l:
            assert not log_key_error(
                "arg1", 131, "arg31380", [], arg="31", kwarg=231)
        assert "131" in l.output[0]


class TestTaskTypeInfo(TestCase):

    def test_init(self):
        tti = CoreTaskTypeInfo("Name1", "Definition1",
                               "Options", "builder")
        assert tti.name == "Name1"
        assert tti.options == "Options"
        assert tti.task_builder_type == "builder"
        assert tti.definition == "Definition1"
        assert tti.output_formats == []
        assert tti.output_file_ext == []

        tti = CoreTaskTypeInfo("Name2", "Definition2", "Options2",
                               "builder2")
        assert tti.name == "Name2"
        assert tti.options == "Options2"
        assert tti.task_builder_type == "builder2"
        assert tti.definition == "Definition2"
        assert tti.output_formats == []
        assert tti.output_file_ext == []

    def test_preview_methods(self):
        assert CoreTaskTypeInfo.get_task_border("subtask1", None, 10) == []


class TestCoreTaskBuilder(TestCase):

    @staticmethod
    def _get_core_task_builder():
        return CoreTaskBuilder(MagicMock(), MagicMock(), MagicMock())

    @staticmethod
    def _get_task_def_dict(
            output_path: str,
            output_format: Optional[str] = ''
    ) -> dict:
        return {
            'options': {
                'output_path': output_path,
                'format': output_format
            }
        }

    def test_init(self):
        builder = self._get_core_task_builder()
        assert builder.task_definition is not None
        assert builder.owner is not None
        assert isinstance(builder.dir_manager, MagicMock)

    def test_get_task_kwargs(self):
        builder = self._get_core_task_builder()

        class C(object):
            pass

        c = C()
        kwargs = builder.get_task_kwargs(arg1="arg1", arg2=1380, arg3=c)
        assert kwargs["arg1"] == "arg1"
        assert kwargs["arg2"] == 1380
        assert kwargs["arg3"] == c
        assert kwargs["owner"] is not None
        assert isinstance(kwargs["task_definition"], MagicMock)

    @freeze_time('2019-01-01 00:00:00')
    def test_get_output_path_returns_correct_path(self):
        builder = self._get_core_task_builder()
        task_name = 'test_task'
        task_dir_name = f'{task_name}_2019-01-01_00-00-00'

        with TemporaryDirectory() as output_path:
            task_def = self._get_task_def_dict(output_path, 'png')
            mock_definition = MagicMock()
            mock_definition.name = task_name

            result_path = builder.get_output_path(task_def, mock_definition)

            self.assertEquals(
                result_path,
                os.path.join(output_path, task_dir_name, task_name)
            )
