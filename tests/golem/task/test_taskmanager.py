from golem_messages.message import ComputeTaskDef
import os
import random
import shutil
import time
import uuid
from collections import OrderedDict
from unittest.mock import Mock, patch

from apps.core.task.coretaskstate import TaskDefinition
from apps.blender.task.blenderrendertask import BlenderRenderTask
from golem import testutils
from golem.core.common import get_timestamp_utc, timeout_to_deadline
from golem.core.keysauth import EllipticalKeysAuth
from golem.network.p2p.node import Node
from golem.resource import dirmanager
from golem.task.taskbase import Task, TaskHeader, \
    TaskEventListener, ResultType
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import SubtaskStatus, SubtaskState, TaskState, \
    TaskStatus, ComputerState
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
        self.task_definition.full_task_timeout = 10
        self.tmp_dir = None

    def query_extra_data(self, *args, **kwargs):
        return self.query_extra_data_return_value

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
            task_persistence=True
        )
        self.tm.key_id = "KEYID"
        self.tm.listen_address = "10.10.10.10"
        self.tm.listen_port = 2222

    def tearDown(self):
        super(TestTaskManager, self).tearDown()
        shutil.rmtree(str(self.tm.tasks_dir))

    def _get_task_header(self, task_id, timeout, subtask_timeout):
        return TaskHeader(
            node_name="test_node_%s" % (self.test_nonce,),
            task_id=task_id,
            task_owner_address="task_owner_address_%s" % (self.test_nonce,),
            task_owner_port="task_owner_port_%s" % (self.test_nonce,),
            task_owner_key_id="task_owner_key_id_%s" % (self.test_nonce,),
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

        ctd = ComputeTaskDef()
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ctd['environment'] = "DEFAULT"
        ctd['deadline'] = timeout_to_deadline(subtask_timeout)

        task_mock.query_extra_data_return_value = Task.ExtraData(should_wait=False, ctd=ctd)
        Task.get_progress = Mock()
        task_mock.get_progress.return_value = 0.3

        return task_mock

    def test_start_task(self):
        task_mock = self._get_task_mock()

        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)

        with self.assertRaises(RuntimeError):
            self.tm.start_task(task_mock.header.task_id)

        with self.assertLogs(logger, level="WARNING") as l:
            self.tm.start_task(str(uuid.uuid4()))
        assert any("This is not my task" in log for log in l.output)

    def _get_test_dummy_task(self, task_id):
        defaults = DummyTaskDefaults()
        tdd = DummyTaskDefinition(defaults)
        dm = DirManager(self.path)
        dtb = DummyTaskBuilder("MyNodeName", tdd, self.path, dm)

        dummy_task = dtb.build()
        header = self._get_task_header(task_id=task_id, timeout=120.0,
                              subtask_timeout=120.0)
        dummy_task.header=header

        return dummy_task

    def test_dump_and_restore(self):

        task_ids = ["xyz0", "xyz1"]
        tasks =  [ self._get_test_dummy_task(task_id) for task_id in task_ids]

        with self.assertLogs(logger, level="DEBUG") as l:
            keys_auth = Mock()
            keys_auth.sign.return_value = 'sig_%s' % (self.test_nonce,)
            temp_tm = TaskManager("ABC",Node(),
                keys_auth=keys_auth,
                root_path=self.path,
                task_persistence=True)

            temp_tm.key_id = "KEYID"
            temp_tm.listen_address = "10.10.10.10"
            temp_tm.listen_port = 2222

            for task,task_id in zip(tasks,task_ids ):
                temp_tm.add_new_task(task)
                temp_tm.start_task(task.header.task_id)
                assert any("TASK %s DUMPED" % task_id in log for log in l.output)

        with self.assertLogs(logger, level="DEBUG") as l:
            fresh_tm = TaskManager("ABC", Node(), keys_auth=Mock(),
                                 root_path=self.path, task_persistence=True)

            assert any("SEARCHING FOR TASKS TO RESTORE" in log for log in l.output)
            assert any("RESTORE TASKS" in log for log in l.output)

            for task,task_id in zip(tasks,task_ids ):
                restored_task = fresh_tm.tasks[task.header.task_id]
                assert any("TASK %s RESTORED" % task_id in log for log in l.output)
                # check some task's properties...
                assert restored_task.header.task_id == task.header.task_id

    def test_remove_wrong_task_during_restore(self):
        broken_pickle_file = self.tm.tasks_dir / "broken.pickle"
        with broken_pickle_file.open('w') as f:
            f.write("notapickle")
        assert broken_pickle_file.is_file()
        self.tm.restore_tasks()
        assert not broken_pickle_file.is_file()


    @patch('golem.task.taskbase.Task.needs_computation', return_value=True)
    def test_get_next_subtask(self, *_):
        assert isinstance(self.tm, TaskManager)

        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert wrong_task

        task_mock = self._get_task_mock()

        # Task's initial state is set to 'notStarted' (found in activeStatus)
        self.tm.add_new_task(task_mock)
        self.tm.start_task(task_mock.header.task_id)

        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is not None
        assert not wrong_task

        self.tm.tasks_states["xyz"].status = self.tm.activeStatus[0]
        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 1, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 2, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "xyzxyz"
        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        task_state = self.tm.tasks_states["xyz"]
        self.assertIsInstance(subtask, ComputeTaskDef)
        assert not wrong_task
        subtask_state = task_state.subtask_states[subtask['subtask_id']]
        assert subtask_state.computer.price == 1010

        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "xyzxyz2"
        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 20000, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)
        assert not wrong_task

        del self.tm.subtask2task_mapping["xyzxyz2"]
        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None

        del self.tm.tasks_states["xyz"].subtask_states["xyzxyz2"]
        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)

        task_mock.query_extra_data_return_value.ctd['subtask_id'] = None
        subtask, wrong_task, wait = self.tm.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None

        self.tm.delete_task("xyz")
        assert self.tm.tasks.get("xyz") is None
        assert self.tm.tasks_states.get("xyz") is None

    def test_delete_task_with_dump(self):
        task_id = "xyz"
        task = self._get_test_dummy_task(task_id)
        with self.assertLogs(logger, level="DEBUG") as l:
            self.tm.add_new_task(task)
            self.tm.start_task(task.header.task_id)
            assert any("TASK %s DUMPED" % task_id in log for log in l.output)
            assert any("Task %s added" % task_id in log for log in l.output)

            paf = self.tm._dump_filepath(task_id)
            assert paf.is_file()
            self.tm.delete_task(task_id)
            assert self.tm.tasks.get(task_id) is None
            assert self.tm.tasks_states.get(task_id) is None
            assert not paf.is_file()

    def test_get_and_set_value(self):
        with self.assertLogs(logger, level="WARNING") as l:
            self.tm.set_value("xyz", "xxyyzz", 13)
        assert any("not my task" in log for log in l.output)
        with self.assertLogs(logger, level="WARNING"):
            self.tm.get_value("xxyyzz")

        with self.assertLogs(logger, level="WARNING"):
            self.tm.set_computation_time("xxyyzz", 12)

        task_mock = self._get_task_mock()

        self.tm.add_new_task(task_mock)
        with self.assertLogs(logger, level="WARNING") as l:
            self.tm.set_value("xyz", "xxyyzz", 13)
        assert any("not my subtask" in log for log in l.output)

        self.tm.tasks_states["xyz"].status = self.tm.activeStatus[0]
        with patch('golem.task.taskbase.Task.needs_computation', return_value=True):
            subtask, wrong_task, wait = self.tm.get_next_subtask(
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

        self.tm.set_value("xyz", "xxyyzz", 13)
        self.assertEqual(self.tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 13)
        self.assertEqual(self.tm.get_value("xxyyzz"), 13)

        self.tm.set_computation_time("xxyyzz", 3601)
        self.assertEqual(self.tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 1011)

    def test_change_config(self):
        self.assertTrue(self.tm.use_distributed_resources)
        self.tm.change_config(self.path, False)
        self.assertFalse(self.tm.use_distributed_resources)

    @patch('golem.task.taskmanager.TaskManager.dump_task')
    def test_computed_task_received(self, dump_mock):
        th = TaskHeader("ABC", "xyz", "10.10.10.10", 1024, "key_id", "DEFAULT")
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
                ctd = ComputeTaskDef()
                ctd['task_id'] = self.header.task_id
                ctd['subtask_id'] = self.subtasks_id[0]
                ctd['environment'] = "DEFAULT"
                self.subtasks_id = self.subtasks_id[1:]
                e = self.ExtraData(False, ctd)
                return e

            def needs_computation(self):
                return sum(self.finished.values()) != len(self.finished)

            def computation_finished(self, subtask_id, task_result,
                                     result_type=ResultType.DATA):
                if not self.restarted[subtask_id]:
                    self.finished[subtask_id] = True

            def verify_subtask(self, subtask_id):
                return self.verify_subtasks[subtask_id]

            def finished_computation(self):
                return not self.needs_computation()

            def verify_task(self):
                return self.finished_computation()

            def restart_subtask(self, subtask_id):
                self.restarted[subtask_id] = True

        t = TestTask(th, "print 'Hello world'", ["xxyyzz"], verify_subtasks={"xxyyzz": True})
        self.tm.add_new_task(t)
        self.tm.start_task(t.header.task_id)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd['subtask_id'] == "xxyyzz"
        assert not should_wait
        task_id = self.tm.subtask2task_mapping["xxyyzz"]
        assert task_id == "xyz"
        ss = self.tm.tasks_states["xyz"].subtask_states["xxyyzz"]
        assert ss.subtask_status == SubtaskStatus.starting
        assert self.tm.computed_task_received("xxyyzz", [], 0)
        assert t.finished["xxyyzz"]
        assert ss.subtask_progress == 1.0
        assert ss.subtask_rem_time == 0.0
        assert ss.subtask_status == SubtaskStatus.finished
        assert self.tm.tasks_states["xyz"].status == TaskStatus.finished

        th.task_id = "abc"
        t2 = TestTask(th, "print 'Hello world'", ["aabbcc"], verify_subtasks={"aabbcc": True})
        self.tm.add_new_task(t2)
        self.tm.start_task(t2.header.task_id)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "abc", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd['subtask_id'] == "aabbcc"
        assert not should_wait
        self.tm.restart_subtask("aabbcc")
        ss = self.tm.tasks_states["abc"].subtask_states["aabbcc"]
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not self.tm.computed_task_received("aabbcc", [], 0)
        assert ss.subtask_progress == 0.0
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not t2.finished["aabbcc"]

        th.task_id = "qwe"
        t3 = TestTask(th, "print 'Hello world!", ["qqwwee", "rrttyy"], {"qqwwee": True, "rrttyy": True})
        self.tm.add_new_task(t3)
        self.tm.start_task(t3.header.task_id)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "qwe", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd['subtask_id'] == "qqwwee"
        self.tm.task_computation_failure("qqwwee", "something went wrong")
        ss = self.tm.tasks_states["qwe"].subtask_states["qqwwee"]
        assert ss.subtask_status == SubtaskStatus.failure
        assert ss.subtask_progress == 1.0
        assert ss.subtask_rem_time == 0.0
        assert ss.stderr == "something went wrong"
        with self.assertLogs(logger, level="WARNING"):
            assert not self.tm.computed_task_received("qqwwee", [], 0)

        th.task_id = "task4"
        t2 = TestTask(th, "print 'Hello world!", ["ttt4", "sss4"], {'ttt4': False, 'sss4': True})
        self.tm.add_new_task(t2)
        self.tm.start_task(t2.header.task_id)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2,
                                                           "10.10.10.10")
        assert not wrong_task
        assert ctd['subtask_id'] == "ttt4"
        assert not self.tm.computed_task_received("ttt4", [], 0)
        assert self.tm.tasks_states["task4"].subtask_states["ttt4"].subtask_status == SubtaskStatus.failure
        assert not self.tm.computed_task_received("ttt4", [], 0)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert not wrong_task
        assert ctd['subtask_id'] == "sss4"
        assert self.tm.computed_task_received("sss4", [], 0)


    @patch('golem.task.taskmanager.TaskManager.dump_task')
    def test_task_result_incoming(self, dump_mock):
        subtask_id = "xxyyzz"
        node_id = 'node'

        task_mock = self._get_task_mock()
        task_mock.counting_nodes = {}

        with patch("golem.task.taskbase.Task.result_incoming") as result_incoming_mock:
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

        with patch("golem.task.taskbase.Task.result_incoming") as result_incoming_mock:
            self.tm.task_result_incoming(subtask_id)
            assert result_incoming_mock.called
            assert dump_mock.called

        self.tm.tasks = []
        with patch("golem.task.taskbase.Task.result_incoming") as result_incoming_mock:
            self.tm.task_result_incoming(subtask_id)
            assert not result_incoming_mock.called

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

        self.tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        self.tm.get_next_subtask("NODEID", "NODENAME", "TASK 1", 1000, 100, 10000, 10000)
        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "aabbcc"
        self.tm.get_next_subtask("NODEID2", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        task_mock.query_extra_data_return_value.ctd['subtask_id'] = "ddeeff"
        self.tm.get_next_subtask("NODEID3", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        self.assertEqual(set(self.tm.get_subtasks("xyz")), {"xxyyzz", "aabbcc", "ddeeff"})
        assert self.tm.get_subtasks("TASK 1") == ["SUBTASK 1"]

    def test_resource_send(self):
        from pydispatch import dispatcher
        self.tm.task_persistence = True
        t = Task(TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "abcde", "DEFAULT"), "print 'hello world'", None)
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
            self.assertEqual(listener_mock.call_count, 3)
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
        with patch('golem.task.taskbase.Task.needs_computation', return_value=True):
            t2 = self._get_task_mock(task_id="abc", subtask_id="aabbcc", timeout=10, subtask_timeout=0.1)
            self.tm.add_new_task(t2)
            self.tm.start_task(t2.header.task_id)
            self.tm.get_next_subtask("ABC", "ABC", "abc", 1000, 10, 5, 10, 2, "10.10.10.10")
            time.sleep(0.1)
            self.tm.check_timeouts()
            assert self.tm.tasks_states["abc"].status == TaskStatus.waiting
            assert self.tm.tasks_states["abc"].subtask_states["aabbcc"].subtask_status == SubtaskStatus.failure
        # Task with task and subtask timeout
        with patch('golem.task.taskbase.Task.needs_computation', return_value=True):
            t3 = self._get_task_mock(task_id="qwe", subtask_id="qwerty", timeout=0.1, subtask_timeout=0.1)
            self.tm.add_new_task(t3)
            self.tm.start_task(t3.header.task_id)
            self.tm.get_next_subtask("ABC", "ABC", "qwe", 1000, 10, 5, 10, 2, "10.10.10.10")
            time.sleep(0.1)
            self.tm.check_timeouts()
            assert self.tm.tasks_states["qwe"].status == TaskStatus.timeout
            assert self.tm.tasks_states["qwe"].subtask_states["qwerty"].subtask_status == SubtaskStatus.failure

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
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.abort_task("xyz")

        assert self.tm.tasks_states["xyz"].status == TaskStatus.aborted

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_tasks(self, _):
        count = 3

        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path)
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
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path)
        task_id, _ = self.__build_tasks(tm, 1)

        tm.get_task_preview(task_id)
        assert get_preview.called

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_subtasks_borders(self, _):
        count = 3
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path)
        task_id, _ = self.__build_tasks(tm, count)

        borders = tm.get_subtasks_borders(task_id, 0)
        assert len(borders) == 0

        borders = tm.get_subtasks_borders(task_id, 1)
        assert len(borders) == 3
        assert all(len(b) == 4 for b in list(borders.values()))

        borders = tm.get_subtasks_borders(task_id, 2)
        assert len(borders) == 0

    def test_change_timeouts(self):
        t = self._get_task_mock(timeout=20, subtask_timeout=40)
        self.tm.add_new_task(t)
        assert get_timestamp_utc() + 15 <= t.header.deadline
        assert t.header.deadline <= get_timestamp_utc() + 20
        assert t.header.subtask_timeout == 40
        self.tm.change_timeouts("xyz", 60, 10)
        assert get_timestamp_utc() + 55 <= t.header.deadline
        assert t.header.deadline <= get_timestamp_utc() + 60
        assert t.header.subtask_timeout == 10

    def test_update_signatures(self):

        node = Node(
            node_name="node", key="key_id", prv_addr="10.0.0.10",
            prv_port=40103, pub_addr="1.2.3.4", pub_port=40103,
            p2p_prv_port=40102, p2p_pub_port=40102
        )
        task = Task(TaskHeader("node", "task_id", "1.2.3.4", 1234,
                               "key_id", "environment", task_owner=node), '',
                    TaskDefinition())

        self.tm.keys_auth = EllipticalKeysAuth(self.path)
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
        with self.assertRaises(TypeError):
            self.tm.set_value(task_id, subtask_id, "incorrect value")
        self.tm.key_id = None
        self.tm.listen_address = "not address"
        self.tm.listen_port = "not a port"
        t = self._get_task_mock(task_id="qaz123WSX2", subtask_id="qweasdzxc")
        with self.assertRaises(ValueError):
            self.tm.add_new_task(t)
        self.tm.key_id = "1"
        with self.assertRaises(IOError):
            self.tm.add_new_task(t)

    def test_restart_frame_subtasks(self):
        tm = self.tm
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
        for task_id in list(tm.tasks):
            for i in range(3):
                tm.restart_frame_subtasks(task_id, i + 1)
        assert tm.notice_task_updated.called

        subtask_states = {}

        for task in list(tm.tasks.values()):
            task_state = tm.tasks_states[task.header.task_id]
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
            definition.full_task_timeout = 3671 * 10
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

            task = BlenderRenderTask(node_name='node',
                                     task_definition=definition,
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
            task.preview_updater.get_offset = Mock(wraps=lambda part: part*10)
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
