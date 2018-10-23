import os
import random
import shutil
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from freezegun import freeze_time
from golem_messages.message import ComputeTaskDef
from golem_messages import factories as msg_factories
from pydispatch import dispatcher
from twisted.internet.defer import fail
from twisted.trial.unittest import TestCase as TwistedTestCase

from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import TaskDefinition
from apps.blender.task.blenderrendertask import BlenderRenderTask
from golem import testutils
from golem.core.common import timeout_to_deadline
from golem.core.keysauth import KeysAuth
from golem.network.p2p.node import Node
from golem.resource import dirmanager
from golem.task.taskbase import Task, TaskHeader, \
    TaskEventListener, ResultType, AcceptClientVerdict
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import SubtaskStatus, SubtaskState, TaskState, \
    TaskStatus, ComputerState, TaskOp, SubtaskOp, OtherOp
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithreactor import TestDirFixtureWithReactor

from apps.dummy.task.dummytask import (
    DummyTaskDefaults,
    DummyTaskBuilder)
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
from golem.resource.dirmanager import DirManager


class PickableMock(Mock):
    # to make the mock pickable
    def __reduce__(self):
        return (Mock, ())


class TaskMock(Task):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_definition = Mock()
        self.task_definition.timeout = 10
        self.tmp_dir = None

    def query_extra_data(self, *args, **kwargs):
        return self.query_extra_data_return_value

    def get_total_tasks(self):
        return 0

    def __getstate__(self):
        state = super(TaskMock, self).__getstate__()
        del state['query_extra_data_return_value']
        return state

    # to make the mock pickable
    def __reduce__(self):
        return (Mock, ())


@patch.multiple(TaskMock, __abstractmethods__=frozenset())
@patch.multiple(Task, __abstractmethods__=frozenset())
class TestTaskManager(LogTestCase, TestDirFixtureWithReactor,
                      testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/task/taskmanager.py',
    ]

    def setUp(self):
        super(TestTaskManager, self).setUp()
        random.seed()
        self.test_nonce = "%.3f-%d" % (time.time(), random.random() * 10000)
        keys_auth = Mock()
        keys_auth.sign.return_value = 'sig_%s' % (self.test_nonce,)
        self.tm = TaskManager(
            "ABC",
            Node(),
            keys_auth,
            root_path=self.path,
            task_persistence=True,
            finished_cb=Mock()
        )
        self.tm.key_id = "KEYID"
        self.tm.listen_address = "10.10.10.10"
        self.tm.listen_port = 2222

    def tearDown(self):
        super(TestTaskManager, self).tearDown()
        shutil.rmtree(str(self.tm.tasks_dir))

    def _get_task_header(self, task_id, timeout, subtask_timeout):
        return TaskHeader(
            task_id=task_id,
            task_owner=Node(
                key="task_owner_key_%s" % (self.test_nonce,),
                node_name="test_node_%s" % (self.test_nonce,),
                pub_addr="task_owner_address_%s" % (self.test_nonce,),
                pub_port="task_owner_port_%s" % (self.test_nonce,),
            ),
            environment="test_environ_%s" % (self.test_nonce,),
            resource_size=2 * 1024,
            estimated_memory=3 * 1024,
            max_price=1010,
            deadline=timeout_to_deadline(timeout),
            subtask_timeout=subtask_timeout,
        )

    def _get_task_mock(self, task_id="xyz", subtask_id="xxyyzz", timeout=120.0,
                       subtask_timeout=120.0):
        header = self._get_task_header(task_id, timeout, subtask_timeout)
        task_mock = TaskMock(header, src_code='', task_definition=Mock())
        task_mock.tmp_dir = self.path

        ctd = ComputeTaskDef(
            task_type='Blender',
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory()
        )
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ctd['deadline'] = timeout_to_deadline(subtask_timeout)

        task_mock.query_extra_data_return_value = Task.ExtraData(ctd=ctd)
        Task.get_progress = Mock()
        task_mock.get_progress.return_value = 0.3
        task_mock.accept_client = Mock()
        task_mock.should_accept_client = Mock()
        task_mock.should_accept_client.return_value = \
            AcceptClientVerdict.ACCEPTED

        return task_mock

    def _connect_signal_handler(self):
        handler_called = False
        params = []

        def handler(sender, signal, event, task_id, subtask_id=None, op=None):  # noqa pylint: too-many-arguments
            nonlocal handler_called
            nonlocal params

            handler_called = True
            params.append((sender, signal, event, task_id, subtask_id, op))

        def checker(expected_events):
            self.assertTrue(handler_called, "Handler should have been called")

            for (e_task_id, e_subtask_id, e_op) in expected_events[::-1]:
                sender, signal, event, task_id, subtask_id, op = params.pop()

                self.assertEqual(event, "task_status_updated", "Bad event")
                if e_task_id:
                    self.assertEqual(task_id, e_task_id, "wrong task")
                if e_subtask_id:
                    self.assertIsNotNone(subtask_id, "No subtask_id")
                    self.assertEqual(subtask_id, e_subtask_id, "Bad subtask_id")
                if e_op:
                    self.assertIsNotNone(op, "No operation")
                    self.assertEqual(op, e_op, "Bad operation")

        dispatcher.connect(handler,
                           signal="golem.taskmanager",
                           sender=dispatcher.Any,
                           weak=True)

        return handler, checker

    def test_start_task(self):
        task_mock = self._get_task_mock()

        (handler, checker) = self._connect_signal_handler()
        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)
        checker([("xyz", None, TaskOp.CREATED),
                 ("xyz", None, TaskOp.STARTED)])
        del handler

        with self.assertRaises(RuntimeError):
            self.tm.start_task(task_mock.header.task_id)

        with self.assertLogs(logger, level="WARNING") as log:
            self.tm.start_task(str(uuid.uuid4()))
        assert any("This is not my task" in log for log in log.output)

    def _get_test_dummy_task(self, task_id):
        defaults = DummyTaskDefaults()
        tdd = DummyTaskDefinition(defaults)
        dm = DirManager(self.path)
        dtb = DummyTaskBuilder(Node(node_name="MyNode"), tdd, dm)

        dummy_task = dtb.build()
        header = self._get_task_header(task_id=task_id, timeout=120.0,
                                       subtask_timeout=120.0)
        dummy_task.header = header

        return dummy_task

    def test_dump_and_restore(self):

        task_ids = ["xyz0", "xyz1"]
        tasks = [self._get_test_dummy_task(task_id) for task_id in task_ids]

        with self.assertLogs(logger, level="DEBUG") as log:
            keys_auth = Mock()
            keys_auth.sign.return_value = 'sig_%s' % (self.test_nonce,)
            temp_tm = TaskManager("ABC", Node(),
                                  keys_auth=keys_auth,
                                  root_path=self.path,
                                  task_persistence=True)

            temp_tm.key_id = "KEYID"
            temp_tm.listen_address = "10.10.10.10"
            temp_tm.listen_port = 2222

            for task, task_id in zip(tasks, task_ids):
                temp_tm.add_new_task(task)
                temp_tm.start_task(task.header.task_id)
                assert any(
                    "TASK %s DUMPED" % task_id in log for log in log.output)

        with self.assertLogs(logger, level="DEBUG") as log:
            fresh_tm = TaskManager("ABC", Node(), keys_auth=Mock(),
                                   root_path=self.path, task_persistence=True)

            assert any(
                "SEARCHING FOR TASKS TO RESTORE" in log for log in log.output)
            assert any("RESTORE TASKS" in log for log in log.output)

            for task, task_id in zip(tasks, task_ids):
                assert task.header.task_id == task_id

                restored_task = fresh_tm.tasks[task_id]
                restored_state = fresh_tm.tasks_states[task_id]
                original_state = temp_tm.tasks_states[task_id]

                assert any(
                    "TASK %s RESTORED" % task_id in log for log in log.output)
                # check some task's properties...
                assert restored_task.header.task_id == task_id
                assert original_state.__dict__ == restored_state.__dict__

    def test_remove_wrong_task_during_restore(self):
        broken_pickle_file = self.tm.tasks_dir / "broken.pickle"
        with broken_pickle_file.open('w') as f:
            f.write("notapickle")
        assert broken_pickle_file.is_file()
        self.tm.restore_tasks()
        assert not broken_pickle_file.is_file()

    def test_got_wants_to_compute(self, *_):
        task_mock = self._get_task_mock()
        self.tm.add_new_task(task_mock)

        (handler, checker) = self._connect_signal_handler()
        self.tm.got_wants_to_compute("xyz", "1234", "a name")
        checker([("xyz", None, TaskOp.WORK_OFFER_RECEIVED)])
        del handler

    def test_get_next_subtask_not_my_task(self):

        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert wrong_task

    def test_get_next_subtask_wait_for_node(self):
        task_mock = self._get_task_mock()
        task_mock.should_accept_client.return_value = \
            AcceptClientVerdict.REJECTED

        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)

        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")

        assert subtask is None
        assert not wrong_task

    def test_get_next_subtask_progress_completed(self):
        task_mock = self._get_task_mock()
        task_mock.should_accept_client.return_value = \
            AcceptClientVerdict.ACCEPTED
        task_mock.get_progress.return_value = 1.0

        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)

        wrong_task = not self.tm.is_my_task("xyz")
        assert not wrong_task
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")

        assert subtask is None

    @patch('golem.task.taskbase.Task.needs_computation', return_value=True)
    def test_get_next_subtask(self, *_):
        task_mock = self._get_task_mock()

        # Task's initial state is set to 'notStarted' (found in activeStatus)
        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)

        (handler, checker) = self._connect_signal_handler()
        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is not None
        assert not wrong_task
        checker([("xyz", subtask['subtask_id'], SubtaskOp.ASSIGNED)])
        del handler

        self.tm.tasks_states["xyz"].status = self.tm.activeStatus[0]
        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 1, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 2, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "xyzxyz"
        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        task_state = self.tm.tasks_states["xyz"]
        self.assertIsInstance(subtask, ComputeTaskDef)
        assert not wrong_task
        subtask_state = task_state.subtask_states[subtask['subtask_id']]
        assert subtask_state.computer.price == 1010

        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "xyzxyz2"
        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 20000, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)
        assert not wrong_task

        del self.tm.subtask2task_mapping["xyzxyz2"]
        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None

        del self.tm.tasks_states["xyz"].subtask_states["xyzxyz2"]
        wrong_task = not self.tm.is_my_task("xyz")
        subtask = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)

        self.tm.delete_task("xyz")
        assert self.tm.tasks.get("xyz") is None
        assert self.tm.tasks_states.get("xyz") is None

    def test_check_next_subtask_not_my_task(self):
        checked = self.tm.check_next_subtask("aaa", "aaa", "aaa", 1)
        assert not checked

    def test_should_wait_for_node_not_my_task(self):
        should_wait = self.tm.should_wait_for_node("aaa", "aaa")
        assert not should_wait

    def test_delete_task_with_dump(self):
        task_id = "xyz"
        task = self._get_test_dummy_task(task_id)
        with self.assertLogs(logger, level="DEBUG") as log:
            self.tm.add_new_task(task)
            self.tm.start_task(task.header.task_id)
            assert any("TASK %s DUMPED" % task_id in log for log in log.output)
            assert any("Task %s added" % task_id in log for log in log.output)

            paf = self.tm._dump_filepath(task_id)
            assert paf.is_file()
            self.tm.delete_task(task_id)
            assert self.tm.tasks.get(task_id) is None
            assert self.tm.tasks_states.get(task_id) is None
            assert not paf.is_file()

    def test_get_and_set_value(self):
        with self.assertLogs(logger, level="WARNING"):
            self.tm.get_value("xxyyzz")

        task_mock = self._get_task_mock()

        self.tm.add_new_task(task_mock)

        self.tm.tasks_states["xyz"].status = self.tm.activeStatus[0]
        with patch('golem.task.taskbase.Task.needs_computation',
                   return_value=True):
            wrong_task = not self.tm.is_my_task("xyz")
            subtask = self.tm.get_next_subtask(
                node_id="DEF",
                node_name="DEF",
                task_id="xyz",
                estimated_performance=1000,
                price=10,
                max_resource_size=5,
                max_memory_size=10,
                num_cores=2,
                address="10.10.10.10",
            )
            self.assertIsInstance(subtask, ComputeTaskDef)
            self.assertFalse(wrong_task)

        self.tm.set_subtask_value("xxyyzz", 13)
        self.assertEqual(
            self.tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 13)
        self.assertEqual(self.tm.get_value("xxyyzz"), 13)

    def test_change_config(self):
        self.assertTrue(self.tm.use_distributed_resources)
        self.tm.change_config(self.path, False)
        self.assertFalse(self.tm.use_distributed_resources)

    @patch('golem.task.taskmanager.TaskManager.dump_task')
    def test_computed_task_received(self, _):
        owner = Node(node_name="ABC",
                     pub_addr="10.10.10.10",
                     pub_port=1024,
                     key="key_id")
        th = TaskHeader(task_id="xyz", environment="DEFAULT", task_owner=owner)
        th.max_price = 50

        class TestTask(Task):
            def __init__(self, header, src_code, subtasks_id, verify_subtasks):
                super(TestTask, self).__init__(header, src_code, Mock())
                self.finished = {k: False for k in subtasks_id}
                self.restarted = {k: False for k in subtasks_id}
                self.verify_subtasks = verify_subtasks
                self.subtasks_id = subtasks_id

            def query_extra_data(self, perf_index, num_cores=1, node_id=None,
                                 node_name=None):
                ctd = ComputeTaskDef(
                    task_type='Blender',
                    meta_parameters=msg_factories.tasks. \
                        BlenderScriptPackageFactory()
                )
                ctd['task_id'] = self.header.task_id
                ctd['subtask_id'] = self.subtasks_id[0]
                self.subtasks_id = self.subtasks_id[1:]
                e = self.ExtraData(ctd=ctd)
                return e

            def get_total_tasks(self):
                return 0

            def needs_computation(self):
                return sum(self.finished.values()) != len(self.finished)

            def computation_finished(self, subtask_id, task_result,
                                     result_type=ResultType.DATA,
                                     verification_finished=None):
                if not self.restarted[subtask_id]:
                    self.finished[subtask_id] = True
                verification_finished()

            def verify_subtask(self, subtask_id):
                return self.verify_subtasks[subtask_id]

            def finished_computation(self):
                return not self.needs_computation()

            def verify_task(self):
                return self.finished_computation()

            def restart_subtask(self, subtask_id):
                self.restarted[subtask_id] = True

            def should_accept_client(self, node_id):
                return AcceptClientVerdict.ACCEPTED

            def accept_client(self, node_id):
                return AcceptClientVerdict.ACCEPTED

        t = TestTask(th, "print 'Hello world'", ["xxyyzz"],
                     verify_subtasks={"xxyyzz": True})
        self.tm.add_new_task(t)
        self.tm.start_task(t.header.task_id)
        wrong_task = not self.tm.is_my_task("xyz")
        should_wait = self.tm.should_wait_for_node("xyz", "DEF")
        ctd = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1030, 10, 10000,
                                       10000, 10000)
        assert not wrong_task
        assert ctd['subtask_id'] == "xxyyzz"
        assert not should_wait
        task_id = self.tm.subtask2task_mapping["xxyyzz"]
        assert task_id == "xyz"
        ss = self.tm.tasks_states["xyz"].subtask_states["xxyyzz"]
        assert ss.subtask_status == SubtaskStatus.starting
        self.tm.verification_finished = Mock()
        (handler, checker) = self._connect_signal_handler()
        self.tm.computed_task_received("xxyyzz", [], 0,
                                       self.tm.verification_finished)
        assert self.tm.verification_finished.call_count == 1
        assert t.finished["xxyyzz"]
        assert ss.subtask_progress == 1.0
        assert ss.subtask_rem_time == 0.0
        assert ss.subtask_status == SubtaskStatus.finished
        assert self.tm.tasks_states["xyz"].status == TaskStatus.finished
        checker([("xyz", ctd['subtask_id'], SubtaskOp.FINISHED),
                 ("xyz", None, TaskOp.FINISHED)])
        del handler

        th.task_id = "abc"
        t2 = TestTask(th, "print 'Hello world'", ["aabbcc"],
                      verify_subtasks={"aabbcc": True})
        self.tm.add_new_task(t2)
        self.tm.start_task(t2.header.task_id)
        progress = self.tm.get_progresses()
        assert progress != {}
        wrong_task = not self.tm.is_my_task("abc")
        should_wait = self.tm.should_wait_for_node("abc", "DEF")
        ctd = self.tm.get_next_subtask("DEF", "DEF", "abc", 1030, 10, 10000,
                                       10000, 10000)
        assert not wrong_task
        assert ctd['subtask_id'] == "aabbcc"
        assert not should_wait
        (handler, checker) = self._connect_signal_handler()
        self.tm.restart_subtask("aabbcc")
        ss = self.tm.tasks_states["abc"].subtask_states["aabbcc"]
        assert ss.subtask_status == SubtaskStatus.restarted
        self.tm.computed_task_received("aabbcc", [], 0,
                                       self.tm.verification_finished)
        assert self.tm.verification_finished.call_count == 2
        assert ss.subtask_progress == 0.0
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not t2.finished["aabbcc"]
        checker([("abc", "aabbcc", SubtaskOp.RESTARTED),
                 ("abc", "aabbcc", OtherOp.UNEXPECTED)])
        del handler

        th.task_id = "qwe"
        t3 = TestTask(th, "print 'Hello world!", ["qqwwee", "rrttyy"],
                      {"qqwwee": True, "rrttyy": True})
        self.tm.add_new_task(t3)
        self.tm.start_task(t3.header.task_id)
        wrong_task = not self.tm.is_my_task("qwe")
        should_wait = self.tm.should_wait_for_node("qwe", "DEF")
        ctd = self.tm.get_next_subtask("DEF", "DEF", "qwe", 1030, 10, 10000,
                                       10000, 10000)
        assert not wrong_task
        assert ctd['subtask_id'] == "qqwwee"
        (handler, checker) = self._connect_signal_handler()
        self.tm.task_computation_failure("qqwwee", "something went wrong")
        checker([("qwe", ctd['subtask_id'], SubtaskOp.FAILED)])
        del handler
        ss = self.tm.tasks_states["qwe"].subtask_states["qqwwee"]
        assert ss.subtask_status == SubtaskStatus.failure
        assert ss.subtask_progress == 1.0
        assert ss.subtask_rem_time == 0.0
        assert ss.stderr == "something went wrong"
        with self.assertLogs(logger, level="WARNING"):
            (handler, checker) = self._connect_signal_handler()
            self.tm.computed_task_received(
                "qqwwee", [],
                0,
                self.tm.verification_finished)
            checker([("qwe", "qqwwee", OtherOp.UNEXPECTED)])
            del handler
        assert self.tm.verification_finished.call_count == 3
        th.task_id = "task4"
        t2 = TestTask(th, "print 'Hello world!", ["ttt4", "sss4"],
                      {'ttt4': False, 'sss4': True})
        self.tm.add_new_task(t2)
        self.tm.start_task(t2.header.task_id)
        wrong_task = not self.tm.is_my_task("task4")
        should_wait = self.tm.should_wait_for_node("task4", "DEF")
        ctd = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10,
                                       2, "10.10.10.10")
        assert not wrong_task
        assert ctd['subtask_id'] == "ttt4"
        (handler, checker) = self._connect_signal_handler()
        self.tm.computed_task_received("ttt4", [], 0,
                                       self.tm.verification_finished)
        assert self.tm.verification_finished.call_count == 4
        assert self.tm.tasks_states["task4"].subtask_states[
                   "ttt4"].subtask_status == SubtaskStatus.failure
        self.tm.computed_task_received("ttt4", [], 0,
                                       self.tm.verification_finished)
        assert self.tm.verification_finished.call_count == 5
        wrong_task = not self.tm.is_my_task("task4")
        should_wait = self.tm.should_wait_for_node("task4", "DEF")
        ctd = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10,
                                       2, "10.10.10.10")
        assert not wrong_task
        assert ctd['subtask_id'] == "sss4"
        self.tm.computed_task_received("sss4", [], 0,
                                       self.tm.verification_finished)
        assert self.tm.verification_finished.call_count == 6
        checker([("task4", "ttt4", SubtaskOp.NOT_ACCEPTED),
                 ("task4", "ttt4", OtherOp.UNEXPECTED),
                 ("task4", "sss4", SubtaskOp.ASSIGNED),
                 ("task4", "sss4", SubtaskOp.FINISHED),
                 ("task4", None, TaskOp.FINISHED)])
        del handler

    def test_computed_task_received_failure(self):
        # GIVEN
        task_id = "unittest_task_id"
        subtask_id = "unittest_subtask_id"
        result = Mock()
        result_type = Mock()
        mock_finished = Mock()

        self.tm.notice_task_updated = Mock()
        self.tm.subtask2task_mapping[subtask_id] = task_id

        task_obj = self.tm.tasks[task_id] = Mock()
        task_obj.computation_finished = lambda a, b, c, cb: cb()
        task_obj.finished_computation = Mock(return_value=True)
        task_obj.verify_task = Mock(return_value=False)

        task_state = self.tm.tasks_states[task_id] = Mock()
        task_state.status = TaskStatus.computing
        task_state.subtask_states = dict()

        subtask_state = task_state.subtask_states[subtask_id] = Mock()
        subtask_state.subtask_status = SubtaskStatus.downloading

        # WHEN
        with self.assertLogs(logger, level="DEBUG") as log:
            self.tm.computed_task_received(subtask_id, result, result_type,
                                           mock_finished)

        # THEN
        expected_warn = f"Task finished but was not accepted. " \
                        f"task_id='{task_id}'"
        assert any(expected_warn in s for s in log.output)
        assert self.tm.notice_task_updated.call_count == 2
        self.tm.notice_task_updated.assert_called_with(
            task_id, op=TaskOp.NOT_ACCEPTED)
        mock_finished.assert_called_once()

    @patch('golem.task.taskmanager.TaskManager.dump_task')
    def test_task_result_incoming(self, dump_mock):
        subtask_id = "xxyyzz"
        node_id = 'node'

        task_mock = self._get_task_mock()
        task_mock.counting_nodes = {}

        with patch("golem.task.taskbase.Task.result_incoming") \
                as result_incoming_mock:
            self.tm.task_result_incoming(subtask_id)
            assert not result_incoming_mock.called

        task_mock.subtasks_given = dict()
        task_mock.subtasks_given[subtask_id] = TaskClient(node_id)

        subtask_state = SubtaskState()
        subtask_state.status = SubtaskStatus.downloading
        subtask_state.subtask_id = subtask_id
        subtask_state.computer = Mock()
        subtask_state.computer.node_id = node_id

        task_state = TaskState()
        task_state.computer = Mock()
        task_state.subtask_states[subtask_id] = subtask_state

        self.tm.add_new_task(task_mock)
        self.tm.subtask2task_mapping[subtask_id] = "xyz"
        self.tm.tasks_states["xyz"] = task_state

        with patch("golem.task.taskbase.Task.result_incoming") \
                as result_incoming_mock:
            (handler, checker) = self._connect_signal_handler()
            self.tm.task_result_incoming(subtask_id)
            assert result_incoming_mock.called
            assert dump_mock.called
            checker([("xyz", subtask_id, SubtaskOp.RESULT_DOWNLOADING)])

        self.tm.tasks = []
        with patch("golem.task.taskbase.Task.result_incoming") \
                as result_incoming_mock:
            self.tm.task_result_incoming(subtask_id)
            assert not result_incoming_mock.called

    @patch('golem.task.taskmanager.TaskManager.dump_task')
    def test_task_computation_failure(self, *_):
        # create a task with a single subtask, call task_computation_failure
        # twice; event handler should be called twice, first notifying of
        # subtask failure, then notifying about unexpected subtask
        task_mock = self._get_task_mock()
        task_mock.needs_computation = lambda: True
        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)
        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "aabbcc"
        self.tm.get_next_subtask("NODE", "NODE", "xyz", 1000, 100, 10000, 10000)
        (handler, checker) = self._connect_signal_handler()
        assert self.tm.task_computation_failure("aabbcc",
                                                "something went wrong")
        ss = self.tm.tasks_states["xyz"].subtask_states["aabbcc"]
        assert ss.subtask_status == SubtaskStatus.failure
        assert not self.tm.task_computation_failure("aabbcc",
                                                    "something went wrong")
        checker([("xyz", "aabbcc", SubtaskOp.FAILED),
                 ("xyz", "aabbcc", OtherOp.UNEXPECTED)])
        del handler

    @patch('golem.task.taskbase.Task.needs_computation', return_value=True)
    def test_get_subtasks(self, *_):
        assert self.tm.get_subtasks("Task 1") is None

        task_mock = self._get_task_mock()
        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)
        task_mock2 = self._get_task_mock("TASK 1", "SUBTASK 1")

        self.tm.add_new_task(task_mock2)
        self.tm.start_task(task_mock2.header.task_id)
        assert self.tm.get_subtasks("xyz") == []
        assert self.tm.get_subtasks("TASK 1") == []

        self.tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000,
                                 10000)
        self.tm.get_next_subtask("NODEID", "NODENAME", "TASK 1", 1000, 100,
                                 10000, 10000)
        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "aabbcc"
        self.tm.get_next_subtask("NODEID2", "NODENAME", "xyz", 1000, 100, 10000,
                                 10000)
        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "ddeeff"
        self.tm.get_next_subtask("NODEID3", "NODENAME", "xyz", 1000, 100, 10000,
                                 10000)
        self.assertEqual(set(self.tm.get_subtasks("xyz")),
                         {"xxyyzz", "aabbcc", "ddeeff"})
        assert self.tm.get_subtasks("TASK 1") == ["SUBTASK 1"]

    def test_resource_send(self):
        # pylint: disable=abstract-class-instantiated
        from pydispatch import dispatcher
        self.tm.task_persistence = True
        owner = Node(node_name="ABC",
                     pub_addr="10.10.10.10",
                     pub_port=1023,
                     key="abcde")
        t = TaskMock(
            TaskHeader(task_id="xyz", environment="DEFAULT", task_owner=owner),
            "print 'hello world'", None)
        listener_mock = Mock()

        def listener(sender, signal, event, task_id):
            self.assertEqual(event, 'task_status_updated')
            self.assertEqual(task_id, t.header.task_id)
            listener_mock()

        dispatcher.connect(listener, signal='golem.taskmanager')
        try:
            self.tm.add_new_task(t)
            self.tm.start_task(t.header.task_id)
            self.tm.resources_send("xyz")
            self.assertEqual(3, listener_mock.call_count)
        finally:
            dispatcher.disconnect(listener, signal='golem.taskmanager')

    def test_check_timeouts(self):
        # Task with timeout
        t = self._get_task_mock(timeout=0.05)
        self.tm.add_new_task(t)
        assert self.tm.tasks_states["xyz"].status == TaskStatus.notStarted
        self.tm.start_task(t.header.task_id)
        assert self.tm.tasks_states["xyz"].status in self.tm.activeStatus
        time.sleep(0.1)
        self.tm.check_timeouts()
        assert self.tm.tasks_states['xyz'].status == TaskStatus.timeout
        # Task with subtask timeout
        with patch('golem.task.taskbase.Task.needs_computation',
                   return_value=True):
            t2 = self._get_task_mock(task_id="abc", subtask_id="aabbcc",
                                     timeout=10, subtask_timeout=0.1)
            self.tm.add_new_task(t2)
            self.tm.start_task(t2.header.task_id)
            self.tm.get_next_subtask("ABC", "ABC", "abc", 1000, 10, 5, 10, 2,
                                     "10.10.10.10")
            time.sleep(0.1)
            self.tm.check_timeouts()
            assert self.tm.tasks_states["abc"].status == TaskStatus.waiting
            assert self.tm.tasks_states["abc"].subtask_states[
                       "aabbcc"].subtask_status == SubtaskStatus.failure
        # Task with task and subtask timeout
        with patch('golem.task.taskbase.Task.needs_computation',
                   return_value=True):
            t3 = self._get_task_mock(task_id="qwe", subtask_id="qwerty",
                                     timeout=0.1, subtask_timeout=0.1)
            self.tm.add_new_task(t3)
            self.tm.start_task(t3.header.task_id)
            self.tm.get_next_subtask("ABC", "ABC", "qwe", 1000, 10, 5, 10, 2,
                                     "10.10.10.10")
            time.sleep(0.1)
            (handler, checker) = self._connect_signal_handler()
            self.tm.check_timeouts()
            assert self.tm.tasks_states["qwe"].status == TaskStatus.timeout
            assert self.tm.tasks_states["qwe"].subtask_states[
                "qwerty"].subtask_status == SubtaskStatus.failure
            checker([("qwe", "qwerty", SubtaskOp.TIMEOUT),
                     ("qwe", None, TaskOp.TIMEOUT)])
            del handler

    def test_task_event_listener(self):
        self.tm.notice_task_updated = Mock()
        assert isinstance(self.tm, TaskEventListener)
        self.tm.notify_update_task("xyz")
        self.tm.notice_task_updated.assert_called_with("xyz")

    def test_query_task_state(self):
        with self.assertLogs(logger, level="WARNING"):
            assert self.tm.query_task_state("xyz") is None

        t = self._get_task_mock()
        self.tm.add_new_task(t)
        with self.assertNoLogs(logger, level="WARNING"):
            ts = self.tm.query_task_state("xyz")
        assert ts is not None
        assert ts.progress == 0.3

    def test_abort_task(self):
        with self.assertLogs(logger, level="WARNING"):
            self.assertIsNone(self.tm.abort_task("xyz"))

        t = self._get_task_mock()
        self.tm.add_new_task(t)
        (handler, checker) = self._connect_signal_handler()
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.abort_task("xyz")

        assert self.tm.tasks_states["xyz"].status == TaskStatus.aborted
        checker([("xyz", None, TaskOp.ABORTED)])
        del handler

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_tasks(self, _):
        count = 3
        apps_manager = AppsManager()
        apps_manager.load_all_apps()
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path,
                         apps_manager=apps_manager)
        task_id, subtask_id = self.__build_tasks(tm, count)

        one_task = tm.get_task_dict(task_id)
        assert one_task
        assert isinstance(one_task, dict)
        assert len(one_task)

        all_tasks = tm.get_tasks_dict()
        assert all_tasks
        assert isinstance(all_tasks, list)
        assert len(all_tasks) == count
        assert all(isinstance(t, dict) for t in all_tasks)

        one_subtask = tm.get_subtask_dict(subtask_id)
        assert isinstance(one_subtask, dict)
        assert len(one_subtask)

        all_subtasks = tm.get_subtasks_dict(task_id)
        assert all_subtasks
        assert isinstance(all_subtasks, list)
        assert all(isinstance(t, dict) for t in all_subtasks)

    @patch('golem.network.p2p.node.Node.collect_network_info')
    @patch('apps.blender.task.blenderrendertask.'
           'BlenderTaskTypeInfo.get_preview')
    def test_get_task_preview(self, get_preview, _):
        apps_manager = AppsManager()
        apps_manager.load_all_apps()
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path,
                         apps_manager=apps_manager)
        task_id, _ = self.__build_tasks(tm, 1)

        tm.get_task_preview(task_id)
        assert get_preview.called

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_subtasks_borders(self, _):
        count = 3
        apps_manager = AppsManager()
        apps_manager.load_all_apps()
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path,
                         apps_manager=apps_manager)
        task_id, _ = self.__build_tasks(tm, count)

        borders = tm.get_subtasks_borders(task_id, 0)
        assert len(borders) == 0

        borders = tm.get_subtasks_borders(task_id, 1)
        assert len(borders) == 3
        assert all(len(b) == 4 for b in list(borders.values()))

        borders = tm.get_subtasks_borders(task_id, 2)
        assert len(borders) == 0

    def test_update_signatures(self):
        # pylint: disable=abstract-class-instantiated

        node = Node(
            node_name="node", key="key_id", prv_addr="10.0.0.10",
            prv_port=40103, pub_addr="1.2.3.4", pub_port=40103,
            p2p_prv_port=40102, p2p_pub_port=40102
        )
        task = TaskMock(
            header=TaskHeader(
                task_id="task_id",
                environment="environment",
                task_owner=node),
            src_code='',
            task_definition=TaskDefinition())

        self.tm.keys_auth = KeysAuth(self.path, 'priv_key', 'password')
        self.tm.add_new_task(task)
        sig = task.header.signature

        self.tm.update_task_signatures()
        assert task.header.signature == sig

        task.header.task_owner.pub_port = 40104
        self.tm.update_task_signatures()
        assert task.header.signature != sig

    def test_get_estimated_cost(self):
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path)
        options = {'price': 100,
                   'subtask_time': 1.5,
                   'num_subtasks': 7
                   }
        assert tm.get_estimated_cost("Blender", options) == 1050
        with self.assertLogs(logger, level="WARNING"):
            assert tm.get_estimated_cost("Blender", {}) is None

    def test_errors(self):
        task_id = 'qaz123WSX'
        subtask_id = "qweasdzxc"
        t = self._get_task_mock(task_id=task_id, subtask_id=subtask_id)
        self.tm.add_new_task(t)
        with self.assertRaises(RuntimeError):
            self.tm.add_new_task(t)
        self.tm.key_id = None
        self.tm.listen_address = "not address"
        self.tm.listen_port = "not a port"
        t = self._get_task_mock(task_id="qaz123WSX2", subtask_id="qweasdzxc")
        with self.assertRaises(ValueError):
            self.tm.add_new_task(t)
        self.tm.key_id = "1"
        with self.assertRaises(IOError):
            self.tm.add_new_task(t)

    def test_put_task_in_restarted_state_two_times(self):
        task_id = 'qaz123WSX'
        subtask_id = "qweasdzxc"
        t = self._get_task_mock(task_id=task_id, subtask_id=subtask_id)
        self.tm.add_new_task(t)

        self.tm.put_task_in_restarted_state(task_id)
        with self.assertRaises(self.tm.AlreadyRestartedError):
            self.tm.put_task_in_restarted_state(task_id)

    def test_restart_frame_subtasks(self):
        tm = self.tm
        old_notice_task_updated = tm.notice_task_updated
        tm.notice_task_updated = Mock()

        # Not existing task
        tm.restart_frame_subtasks('any_id', 1)
        assert not tm.notice_task_updated.called

        # Mock task without subtasks
        tm.tasks['test_id'] = Mock()
        tm.tasks['test_id'].get_subtasks.return_value = None
        tm.restart_frame_subtasks('test_id', 1)
        assert not tm.notice_task_updated.called

        # Create tasks
        tm.tasks.pop('test_id')
        _, subtask_id = self.__build_tasks(tm, 3)

        # Successful call
        # Restore normal notice_task_updated and check if the event
        # handler gets called from notice_task_updated; persistence needs to
        # be off as Mock items don't allow it
        tm.notice_task_updated = old_notice_task_updated
        tm.task_persistence = False
        for task_id in list(tm.tasks):
            (handler, checker) = self._connect_signal_handler()
            for i in range(3):
                tm.restart_frame_subtasks(task_id, i + 1)
            checker([(task_id, None, SubtaskOp.RESTARTED),
                     (task_id, None, SubtaskOp.RESTARTED),
                     (task_id, None, SubtaskOp.RESTARTED),
                     (task_id, None, OtherOp.FRAME_RESTARTED)])
            del handler

        subtask_states = {}

        for task in list(tm.tasks.values()):
            task_state = tm.tasks_states[task.header.task_id]
            assert task_state.status == TaskStatus.computing
            subtask_states.update(task_state.subtask_states)

        for subtask_id, subtask_state in list(subtask_states.items()):
            assert subtask_state.subtask_status == SubtaskStatus.restarted

    def __build_tasks(self, tm, n, fixed_frames=False):
        tm.tasks = OrderedDict()
        tm.tasks_states = dict()
        tm.subtask_states = dict()

        task_id = None
        subtask_id = None
        previews = [None, 'result', ['result_1', 'result_2']]

        for i in range(0, n):
            task_id = str(uuid.uuid4())

            definition = TaskDefinition()
            definition.options = Mock()
            definition.output_format = Mock()

            definition.task_id = task_id
            definition.task_type = "blender"
            definition.subtask_timeout = 3671
            definition.subtask_status = [SubtaskStatus.failure,
                                         SubtaskStatus.finished][i % 2]
            definition.timeout = 3671 * 10
            definition.max_price = 1 * 10 ** 18
            definition.resolution = [1920, 1080]
            definition.resources = [str(uuid.uuid4()) for _ in range(5)]
            definition.output_file = os.path.join(self.tempdir, 'somefile')
            definition.main_scene_file = self.path
            definition.options.frames = list(range(i + 1))

            subtask_states, subtask_id = self.__build_subtasks(n)

            state = TaskState()
            state.status = TaskStatus.waiting
            state.remaining_time = 100 - i
            state.extra_data = dict(result_preview=previews[i % 3])
            state.subtask_states = subtask_states

            task = BlenderRenderTask(task_definition=definition,
                                     owner=Node(node_name='node'),
                                     total_tasks=n,
                                     root_path=self.path)
            task.initialize(dirmanager.DirManager(self.path))
            task.get_total_tasks = Mock()
            task.get_progress = Mock()
            task.get_total_tasks.return_value = i + 2
            task.get_progress.return_value = i * 10
            task.subtask_states = subtask_states

            task.preview_updater = Mock()
            task.preview_updater.preview_res_x = 100
            task.preview_updater.get_offset = Mock(wraps=lambda part: part * 10)
            task.preview_updaters = [Mock()] * n
            task.use_frames = fixed_frames or i % 2 == 0

            task.frames_subtasks = {str(k): [] for k in
                                    definition.options.frames}
            task.frames_subtasks["1"] = list(subtask_states.keys())

            task.subtask_states = subtask_states
            task.subtasks_given = dict()

            for key, entry in list(subtask_states.items()):
                new_item = dict(entry.extra_data)
                new_item['frames'] = definition.options.frames
                new_item['status'] = definition.subtask_status
                task.subtasks_given[key] = new_item

            tm.tasks[task_id] = task
            tm.tasks_states[task_id] = state
            tm.subtask_states.update(subtask_states)

        tm.subtask2task_mapping = self.__build_subtask2task(tm.tasks)
        return task_id, subtask_id

    @staticmethod
    def __build_subtasks(n):

        subtasks = dict()
        subtask_id = None

        for i in range(0, n):
            subtask = SubtaskState()
            subtask.subtask_id = str(uuid.uuid4())
            subtask.subtask_status = SubtaskStatus.starting
            subtask.computer = ComputerState()
            subtask.computer.node_name = 'node_{}'.format(i)
            subtask.computer.node_id = 'deadbeef0{}'.format(i)
            subtask.results = []
            subtask.stderr = 'error_{}'.format(i)
            subtask.stdout = 'output_{}'.format(i)
            subtask.extra_data = {'start_task': i, 'end_task': i}
            subtask_id = subtask.subtask_id

            subtasks[subtask.subtask_id] = subtask

        return subtasks, subtask_id

    @staticmethod
    def __build_subtask2task(tasks):
        subtask2task = dict()
        for k, t in list(tasks.items()):
            for sk, st in list(t.subtask_states.items()):
                subtask2task[st.subtask_id] = t.header.task_id
        return subtask2task

    @patch('golem.task.taskmanager.logger')
    def test_copy_results_invalid_ids(self, logger_mock):
        self.tm.copy_results('invalid_id1', 'invalid_id2', [])
        logger_mock.exception.assert_called_once()

    @patch('golem.task.taskmanager.logger')
    def test_copy_results_invalid_task_class(self, logger_mock):
        self.tm.tasks['old_task_id'] = self._get_task_mock('old_task_id')
        self.tm.tasks['new_task_id'] = self._get_task_mock('new_task_id')
        self.tm.copy_results('old_task_id', 'new_task_id', [])
        logger_mock.exception.assert_called_once()

    @freeze_time()
    def test_copy_results_subtasks_properly_generated(self):
        old_task = MagicMock(spec=CoreTask)
        new_task = MagicMock(spec=CoreTask)
        self.tm.tasks['old_task_id'] = old_task
        self.tm.tasks['new_task_id'] = new_task
        self.tm.tasks_states['new_task_id'] = TaskState()

        new_task.header = MagicMock(max_price=42)
        new_task.subtasks_given = {}
        new_task.last_task = 0
        new_task.num_failed_subtasks = 0

        ctds = [{
            'task_id': 'new_task_id',
            'subtask_id': 'subtask_id1',
            'extra_data': {'start_task': 1},
            'short_description': 'desc1',
            'src_code': 'code1',
            'performance': 1000,
            'deadline': 1000000000
        }, {
            'task_id': 'new_task_id',
            'subtask_id': 'subtask_id2',
            'extra_data': {'start_task': 2},
            'short_description': 'desc2',
            'src_code': 'code2',
            'performance': 2000,
            'deadline': 2000000000
        }]
        ctd_iterator = iter(ctds)

        def query_extra_data(*_, **__):
            ctd = next(ctd_iterator)
            new_task.subtasks_given[ctd['subtask_id']] = ctd['extra_data']
            new_task.last_task += 1
            return Task.ExtraData(ctd=ctd)

        new_task.needs_computation = lambda: new_task.last_task < len(ctds)
        new_task.query_extra_data = query_extra_data

        with patch.object(self.tm, 'notice_task_updated'):
            self.tm.copy_results('old_task_id', 'new_task_id', [])

            self.assertEqual(new_task.num_failed_subtasks, len(ctds))
            self.assertEqual(
                self.tm.subtask2task_mapping.get('subtask_id1'), 'new_task_id')
            self.assertEqual(
                self.tm.subtask2task_mapping.get('subtask_id2'), 'new_task_id')

            subtask_states = self.tm.tasks_states['new_task_id'].subtask_states
            ss1 = subtask_states.get('subtask_id1')
            ss2 = subtask_states.get('subtask_id2')

            self.assertIsInstance(ss1, SubtaskState)
            self.assertIsInstance(ss2, SubtaskState)

            for ss, ctd in zip((ss1, ss2), ctds):
                self.assertEqual(ss.subtask_id, ctd['subtask_id'])
                self.assertEqual(ss.time_started, time.time())
                self.assertEqual(ss.deadline, ctd['deadline'])
                self.assertEqual(ss.extra_data, ctd['extra_data'])
                self.assertEqual(ss.subtask_status, SubtaskStatus.restarted)
                self.assertEqual(
                    ss.subtask_definition, ctd['short_description'])
                self.assertEqual(ss.computer.performance, ctd['performance'])

    def test_copy_results_subtasks_properly_matched(self):
        old_task = MagicMock(spec=CoreTask)
        new_task = MagicMock(spec=CoreTask)
        self.tm.tasks['old_task_id'] = old_task
        self.tm.tasks['new_task_id'] = new_task
        old_task.subtasks_given = {
            'old_subtask_id1': {
                'id': 'old_subtask_id1',
                'start_task': 1
            },
            'old_subtask_id2': {
                'id': 'old_subtask_id2',
                'start_task': 2
            },
            'old_subtask_id3': {
                'id': 'old_subtask_id3',
                'start_task': 3
            }
        }
        new_task.subtasks_given = {
            'new_subtask_id1': {
                'id': 'new_subtask_id1',
                'start_task': 3
            },
            'new_subtask_id2': {
                'id': 'new_subtask_id2',
                'start_task': 2
            },
            'new_subtask_id3': {
                'id': 'new_subtask_id3',
                'start_task': 1
            }
        }
        new_task.needs_computation.return_value = False

        with patch.object(self.tm, 'restart_subtask') as restart, \
                patch.object(self.tm, '_copy_subtask_results') as copy:
            self.tm.copy_results(
                'old_task_id', 'new_task_id', old_task.subtasks_given.keys())
            restart.assert_not_called()
            copy.assert_any_call(
                old_task=old_task,
                new_task=new_task,
                old_subtask=old_task.subtasks_given['old_subtask_id1'],
                new_subtask=new_task.subtasks_given['new_subtask_id3']
            )
            copy.assert_any_call(
                old_task=old_task,
                new_task=new_task,
                old_subtask=old_task.subtasks_given['old_subtask_id2'],
                new_subtask=new_task.subtasks_given['new_subtask_id2']
            )
            copy.assert_any_call(
                old_task=old_task,
                new_task=new_task,
                old_subtask=old_task.subtasks_given['old_subtask_id3'],
                new_subtask=new_task.subtasks_given['new_subtask_id1']
            )

    def test_copy_results_error_in_copying(self):
        old_task = MagicMock(spec=CoreTask)
        new_task = MagicMock(spec=CoreTask)
        self.tm.tasks['old_task_id'] = old_task
        self.tm.tasks['new_task_id'] = new_task
        old_task.subtasks_given = {
            'old_subtask_id': {
                'id': 'old_subtask_id',
                'start_task': 1
            }
        }
        new_task.subtasks_given = {
            'new_subtask_id': {
                'id': 'new_subtask_id',
                'start_task': 1
            }
        }
        new_task.needs_computation.return_value = False

        with patch.object(self.tm, 'restart_subtask') as restart, \
                patch.object(self.tm, '_copy_subtask_results') as copy, \
                patch('golem.task.taskmanager.logger') as logger:

            copy.return_value = fail(OSError())
            self.tm.copy_results(
                'old_task_id', 'new_task_id', old_task.subtasks_given.keys())

            copy.assert_called_once()
            logger.error.assert_called_once()
            restart.assert_called_once_with('new_subtask_id')


class TestCopySubtaskResults(TwistedTestCase):

    def setUp(self):
        self.tm = TaskManager(
            node_name='node_name',
            node=Node(),
            keys_auth=MagicMock(spec=KeysAuth),
            root_path='/tmp',
            task_persistence=False
        )

        zip_patch = patch('golem.task.taskmanager.ZipFile')
        os_patch = patch('golem.task.taskmanager.os')
        shutil_patch = patch('golem.task.taskmanager.shutil')
        self.zip_mock = zip_patch.start()
        self.os_mock = os_patch.start()
        self.shutil_mock = shutil_patch.start()
        self.addCleanup(zip_patch.stop)
        self.addCleanup(os_patch.stop)
        self.addCleanup(shutil_patch.stop)

    def test_copy_subtask_results(self):  # pylint: disable=too-many-locals

        old_task = MagicMock(spec=CoreTask)
        new_task = MagicMock(spec=CoreTask)
        old_task.header = MagicMock(task_id='old_task_id')
        new_task.header = MagicMock(task_id='new_task_id')

        old_task.tmp_dir = '/tmp/old_task/'
        new_task.tmp_dir = '/tmp/new_task/'
        new_task.get_stdout.return_value = 'stdout'
        new_task.get_stderr.return_value = 'stderr'
        new_task.get_results.return_value = ['result']

        old_subtask = {'subtask_id': 'old_subtask_id'}
        new_subtask = {'subtask_id': 'new_subtask_id'}

        old_task_state = TaskState()
        new_task_state = TaskState()
        old_subtask_state = SubtaskState()
        new_subtask_state = SubtaskState()

        old_subtask_state.computer.node_id = 'node_id'
        old_subtask_state.computer.node_name = 'node_name'
        old_subtask_state.computer.eth_account = 'eth_account'
        old_subtask_state.computer.port = 12345
        old_subtask_state.computer.performance = 1000
        old_subtask_state.computer.price = 2000

        old_task_state.subtask_states['old_subtask_id'] = old_subtask_state
        new_task_state.subtask_states['new_subtask_id'] = new_subtask_state

        self.tm.tasks['old_task_id'] = old_task
        self.tm.tasks['new_task_id'] = new_task
        self.tm.subtask2task_mapping['old_subtask_id'] = 'old_task_id'
        self.tm.subtask2task_mapping['new_subtask_id'] = 'new_task_id'
        self.tm.tasks_states['old_task_id'] = old_task_state
        self.tm.tasks_states['new_task_id'] = new_task_state

        self.zip_mock.return_value.__enter__().namelist.return_value = [
            'stdout',
            'stderr',
            'result',
            '.package_desc'
        ]

        def verify(_):
            old_zip_path = Path('/tmp/old_task/old_task_id.old_subtask_id.zip')
            new_zip_path = Path('/tmp/new_task/new_task_id.new_subtask_id.zip')
            extract_path = Path('/tmp/new_task/new_subtask_id')

            self.shutil_mock.copy.assert_called_once_with(
                old_zip_path, new_zip_path)
            self.os_mock.makedirs.assert_called_once_with(extract_path)
            self.zip_mock.assert_called_once_with(new_zip_path, 'r')
            self.zip_mock().__enter__().extractall.assert_called_once_with(
                extract_path)

            results = [
                '/tmp/new_task/new_subtask_id/stdout',
                '/tmp/new_task/new_subtask_id/stderr',
                '/tmp/new_task/new_subtask_id/result'
            ]
            # Normalize paths (for non-posix systems)
            results = [str(Path(result)) for result in results]

            new_task.copy_subtask_results.assert_called_once_with(
                'new_subtask_id', old_subtask, results)

            self.assertEqual(new_subtask_state.subtask_progress, 1.0)
            self.assertEqual(new_subtask_state.subtask_rem_time, 0.0)
            self.assertEqual(
                new_subtask_state.subtask_status, SubtaskStatus.finished)
            self.assertEqual(new_subtask_state.stdout, 'stdout')
            self.assertEqual(new_subtask_state.stderr, 'stderr')
            self.assertEqual(new_subtask_state.results, ['result'])

            self.assertEqual(old_subtask_state.computer.node_id, 'node_id')
            self.assertEqual(old_subtask_state.computer.node_name, 'node_name')
            self.assertEqual(
                old_subtask_state.computer.eth_account, 'eth_account')
            self.assertEqual(old_subtask_state.computer.port, 12345)
            self.assertEqual(old_subtask_state.computer.performance, 1000)
            self.assertEqual(old_subtask_state.computer.price, 2000)

        patch.object(self.tm, 'notice_task_updated').start()
        deferred = self.tm._copy_subtask_results(
            old_task=old_task,
            new_task=new_task,
            old_subtask=old_subtask,
            new_subtask=new_subtask
        )
        deferred.addCallback(verify)
        return deferred
