import os
import random
import shutil
import time
import uuid

from mock import Mock, patch

from apps.core.task.coretask import CoreTask
from golem.core.common import get_timestamp_utc, timeout_to_deadline
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.deferred import sync_wait
from golem.network.p2p.node import Node
from golem.resource.resource import TaskResourceHeader
from golem.task.taskbase import Task, TaskHeader, ComputeTaskDef, TaskEventListener
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import SubtaskStatus, SubtaskState, TaskState, TaskStatus, ComputerState
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithreactor import TestDirFixtureWithReactor


class TaskMock(Task):
    def query_extra_data(self, *args, **kwargs):
        return self.query_extra_data_return_value

    def __getstate__(self):
        state = super(TaskMock, self).__getstate__()
        del state['query_extra_data_return_value']
        return state


class TestTaskManagerWithPersistance(TestDirFixture, LogTestCase):
    def test_restore(self):
        keys_auth = Mock()
        with self.assertLogs(logger, level="DEBUG") as l:
            TaskManager("ABC", Node(), keys_auth, root_path=self.path, task_persistence=True)
        assert any("RESTORE TASKS" in log for log in l.output)


class TestTaskManager(LogTestCase, TestDirFixtureWithReactor):
    def setUp(self):
        super(TestTaskManager, self).setUp()
        random.seed()
        self.test_nonce = "%.3f-%d" % (time.time(), random.random() * 10000)
        keys_auth = Mock()
        keys_auth.sign.return_value = 'sig_%s' % (self.test_nonce,)
        self.tm = TaskManager("ABC", Node(), keys_auth, root_path=self.path)
        self.tm.key_id = "KEYID"
        self.tm.listen_address = "10.10.10.10"
        self.tm.listen_port = 2222
        self.addr_return = ("10.10.10.10", 1111, "Full NAT")

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
            max_price=10000,
            deadline=timeout_to_deadline(timeout),
            subtask_timeout=subtask_timeout,
        )

    def _get_task_mock(self, task_id="xyz", subtask_id="xxyyzz", timeout=120.0,
                       subtask_timeout=120.0):
        header = self._get_task_header(task_id, timeout, subtask_timeout)
        task_mock = TaskMock(header, src_code='')

        ctd = ComputeTaskDef()
        ctd.task_id = task_id
        ctd.subtask_id = subtask_id
        ctd.environment = "DEFAULT"
        ctd.deadline = timeout_to_deadline(subtask_timeout)

        task_mock.query_extra_data_return_value = Task.ExtraData(should_wait=False, ctd=ctd)
        Task.get_progress = Mock()
        task_mock.get_progress.return_value = 0.3

        return task_mock

    @patch('golem.task.taskbase.Task.needs_computation', return_value=True)
    @patch("golem.task.taskmanager.get_external_address")
    def test_get_next_subtask(self, mock_addr, nc_mock):
        mock_addr.return_value = self.addr_return
        assert isinstance(self.tm, TaskManager)

        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert wrong_task

        task_mock = self._get_task_mock()

        # Task's initial state is set to 'waiting' (found in activeStatus)
        sync_wait(self.tm.add_new_task(task_mock), 20)

        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is not None
        assert not wrong_task

        self.tm.tasks_states["xyz"].status = self.tm.activeStatus[0]
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 1, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 2, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        task_mock.query_extra_data_return_value.ctd.subtask_id = "xyzxyz"
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)
        assert not wrong_task
        assert self.tm.tasks_states["xyz"].subtask_states[subtask.subtask_id].computer.price == 10

        task_mock.query_extra_data_return_value.ctd.subtask_id = "xyzxyz2"
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 20000, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert not wrong_task

        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)
        assert not wrong_task

        del self.tm.subtask2task_mapping["xyzxyz2"]
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None

        del self.tm.tasks_states["xyz"].subtask_states["xyzxyz2"]
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)

        task_mock.query_extra_data_return_value.ctd.subtask_id = None
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None

        self.tm.delete_task("xyz")
        assert self.tm.tasks.get("xyz") is None
        assert self.tm.tasks_states.get("xyz") is None

    @patch("golem.task.taskmanager.get_external_address")
    def test_get_and_set_value(self, mock_addr):
        mock_addr.return_value = self.addr_return
        with self.assertLogs(logger, level="WARNING") as l:
            self.tm.set_value("xyz", "xxyyzz", 13)
        assert any("not my task" in log for log in l.output)
        with self.assertLogs(logger, level="WARNING"):
            self.tm.get_value("xxyyzz")

        with self.assertLogs(logger, level="WARNING"):
            self.tm.set_computation_time("xxyyzz", 12)

        task_mock = self._get_task_mock()

        sync_wait(self.tm.add_new_task(task_mock))
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
        self.assertEqual(self.tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 11)

    def test_change_config(self):
        self.assertTrue(self.tm.use_distributed_resources)
        self.tm.change_config(self.path, False)
        self.assertFalse(self.tm.use_distributed_resources)

    @patch("golem.task.taskmanager.get_external_address")
    def test_get_resources(self, mock_addr):
        mock_addr.return_value = self.addr_return
        task_id = "xyz"

        resources = ['first', 'second']

        task_mock = self._get_task_mock()
        with patch('golem.task.taskmanager.TaskManager.get_resources', return_value=resources):
            sync_wait(self.tm.add_new_task(task_mock))
            assert self.tm.get_resources(task_id, task_mock.header) is resources

        task = Task(self._get_task_header("xyz", 120, 120), "print 'hello world'")
        self.tm.tasks["xyz"] = task
        self.tm.get_resources("xyz", TaskResourceHeader(self.path), 0)

    @patch('golem.task.taskmanager.TaskManager.dump_task')
    @patch("golem.task.taskmanager.get_external_address")
    def test_computed_task_received(self, mock_addr, dump_mock):
        mock_addr.return_value = self.addr_return
        th = TaskHeader("ABC", "xyz", "10.10.10.10", 1024, "key_id", "DEFAULT")
        th.max_price = 50

        class TestTask(Task):
            def __init__(self, header, src_code, subtasks_id, verify_subtasks):
                super(TestTask, self).__init__(header, src_code)
                self.finished = {k: False for k in subtasks_id}
                self.restarted = {k: False for k in subtasks_id}
                self.verify_subtasks = verify_subtasks
                self.subtasks_id = subtasks_id

            def query_extra_data(self, perf_index, num_cores=1, node_id=None, node_name=None):

                ctd = ComputeTaskDef()
                ctd.task_id = self.header.task_id
                ctd.subtask_id = self.subtasks_id[0]
                ctd.environment = "DEFAULT"
                ctd.should_wait = False
                self.subtasks_id = self.subtasks_id[1:]
                e = self.ExtraData(False, ctd)
                return e

            def needs_computation(self):
                return sum(self.finished.values()) != len(self.finished)

            def computation_finished(self, subtask_id, task_result, result_type=0):
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
        sync_wait(self.tm.add_new_task(t))
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "xxyyzz"
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
        sync_wait(self.tm.add_new_task(t2))
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "abc", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "aabbcc"
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
        sync_wait(self.tm.add_new_task(t3))
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "qwe", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "qqwwee"
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
        sync_wait(self.tm.add_new_task(t2))
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2,
                                                           "10.10.10.10")
        assert not wrong_task
        assert ctd.subtask_id == "ttt4"
        assert not self.tm.computed_task_received("ttt4", [], 0)
        assert self.tm.tasks_states["task4"].subtask_states["ttt4"].subtask_status == SubtaskStatus.failure
        assert not self.tm.computed_task_received("ttt4", [], 0)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert not wrong_task
        assert ctd.subtask_id == "sss4"
        assert self.tm.computed_task_received("sss4", [], 0)

    @patch("golem.task.taskmanager.get_external_address")
    def test_task_result_incoming(self, mock_addr):
        mock_addr.return_value = self.addr_return
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

        sync_wait(self.tm.add_new_task(task_mock))
        self.tm.subtask2task_mapping[subtask_id] = "xyz"
        self.tm.tasks_states["xyz"] = task_state

        with patch("golem.task.taskbase.Task.result_incoming") as result_incoming_mock:
            self.tm.task_result_incoming(subtask_id)
            assert result_incoming_mock.called

        self.tm.tasks = []
        with patch("golem.task.taskbase.Task.result_incoming") as result_incoming_mock:
            self.tm.task_result_incoming(subtask_id)
            assert not result_incoming_mock.called

    @patch('golem.task.taskbase.Task.needs_computation', return_value=True)
    @patch("golem.task.taskmanager.get_external_address")
    def test_get_subtasks(self, mock_addr, nc_mock):
        mock_addr.return_value = self.addr_return
        assert self.tm.get_subtasks("Task 1") is None

        task_mock = self._get_task_mock()
        sync_wait(self.tm.add_new_task(task_mock))
        task_mock2 = self._get_task_mock("TASK 1", "SUBTASK 1")
        sync_wait(self.tm.add_new_task(task_mock2))
        assert self.tm.get_subtasks("xyz") == []
        assert self.tm.get_subtasks("TASK 1") == []

        self.tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        self.tm.get_next_subtask("NODEID", "NODENAME", "TASK 1", 1000, 100, 10000, 10000)
        task_mock.query_extra_data_return_value.ctd.subtask_id = "aabbcc"
        self.tm.get_next_subtask("NODEID2", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        task_mock.query_extra_data_return_value.ctd.subtask_id = "ddeeff"
        self.tm.get_next_subtask("NODEID3", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        self.assertEquals(set(self.tm.get_subtasks("xyz")), {"xxyyzz", "aabbcc", "ddeeff"})
        assert self.tm.get_subtasks("TASK 1") == ["SUBTASK 1"]

    @patch("golem.task.taskmanager.get_external_address")
    def test_resource_send(self, mock_addr):
        from pydispatch import dispatcher
        mock_addr.return_value = self.addr_return
        self.tm.task_persistence = True
        t = Task(TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "abcde", "DEFAULT"), "print 'hello world'")
        listener_mock = Mock()
        def listener(sender, signal, event, task_id):
            self.assertEquals(event, 'task_status_updated')
            self.assertEquals(task_id, t.header.task_id)
            listener_mock()
        dispatcher.connect(listener, signal='golem.taskmanager')
        try:
            sync_wait(self.tm.add_new_task(t))
            self.tm.resources_send("xyz")
            self.assertEquals(listener_mock.call_count, 2)
        finally:
            dispatcher.disconnect(listener, signal='golem.taskmanager')

    @patch("golem.task.taskmanager.get_external_address")
    def test_check_timeouts(self, mock_addr):
        mock_addr.return_value = self.addr_return
        # Task with timeout
        t = self._get_task_mock(timeout=0.05)
        sync_wait(self.tm.add_new_task(t))
        assert self.tm.tasks_states["xyz"].status in self.tm.activeStatus
        time.sleep(0.1)
        self.tm.check_timeouts()
        assert self.tm.tasks_states['xyz'].status == TaskStatus.timeout
        # Task with subtask timeout
        with patch('golem.task.taskbase.Task.needs_computation', return_value=True):
            t2 = self._get_task_mock(task_id="abc", subtask_id="aabbcc", timeout=10, subtask_timeout=0.1)
            sync_wait(self.tm.add_new_task(t2))
            self.tm.get_next_subtask("ABC", "ABC", "abc", 1000, 10, 5, 10, 2, "10.10.10.10")
            time.sleep(0.1)
            self.tm.check_timeouts()
            assert self.tm.tasks_states["abc"].status == TaskStatus.waiting
            assert self.tm.tasks_states["abc"].subtask_states["aabbcc"].subtask_status == SubtaskStatus.failure
        # Task with task and subtask timeout
        with patch('golem.task.taskbase.Task.needs_computation', return_value=True):
            t3 = self._get_task_mock(task_id="qwe", subtask_id="qwerty", timeout=0.1, subtask_timeout=0.1)
            sync_wait(self.tm.add_new_task(t3))
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

    @patch("golem.task.taskmanager.get_external_address")
    def test_query_task_state(self, mock_addr):
        mock_addr.return_value = self.addr_return
        with self.assertLogs(logger, level="WARNING"):
            assert self.tm.query_task_state("xyz") is None

        t = self._get_task_mock()
        sync_wait(self.tm.add_new_task(t))
        with self.assertNoLogs(logger, level="WARNING"):
            ts = self.tm.query_task_state("xyz")
        assert ts is not None
        assert ts.progress == 0.3

    @patch("golem.task.taskmanager.get_external_address")
    def test_resume_task(self, mock_addr):
        mock_addr.return_value = self.addr_return
        with self.assertLogs(logger, level="WARNING"):
            assert self.tm.resume_task("xyz") is None
        t = self._get_task_mock()
        sync_wait(self.tm.add_new_task(t))
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.resume_task("xyz")
        assert self.tm.tasks["xyz"].task_status == TaskStatus.starting
        assert self.tm.tasks_states["xyz"].status == TaskStatus.starting

    @patch("golem.task.taskmanager.get_external_address")
    def test_restart_task(self, mock_addr):
        mock_addr.return_value = self.addr_return
        with self.assertLogs(logger, level="WARNING"):
            assert self.tm.restart_task("xyz") is None
        t = self._get_task_mock()
        sync_wait(self.tm.add_new_task(t))
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.restart_task("xyz")
        assert self.tm.tasks["xyz"].task_status == TaskStatus.waiting
        assert self.tm.tasks_states["xyz"].status == TaskStatus.waiting
        with patch('golem.task.taskbase.Task.needs_computation', return_value=True):
            self.tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000, 10000)
            t.query_extra_data_return_value.ctd.subtask_id = "xxyyzz2"
            self.tm.get_next_subtask("NODEID2", "NODENAME2", "xyz", 1000, 100, 10000, 10000)
            self.assertEquals(len(self.tm.tasks_states["xyz"].subtask_states), 2)
            with self.assertNoLogs(logger, level="WARNING"):
                self.tm.restart_task("xyz")
            assert self.tm.tasks["xyz"].task_status == TaskStatus.waiting
            assert self.tm.tasks_states["xyz"].status == TaskStatus.waiting
            assert len(self.tm.tasks_states["xyz"].subtask_states) == 2
            for ss in self.tm.tasks_states["xyz"].subtask_states.values():
                assert ss.subtask_status == SubtaskStatus.restarted

    @patch("golem.task.taskmanager.get_external_address")
    def test_abort_task(self, mock_addr):
        mock_addr.return_value = self.addr_return
        with self.assertLogs(logger, level="WARNING"):
            assert self.tm.abort_task("xyz") is None
        t = self._get_task_mock()
        sync_wait(self.tm.add_new_task(t))
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.abort_task("xyz")
        assert self.tm.tasks["xyz"].task_status == TaskStatus.aborted
        assert self.tm.tasks_states["xyz"].status == TaskStatus.aborted

    @patch("golem.task.taskmanager.get_external_address")
    def test_pause_task(self, mock_addr):
        mock_addr.return_value = self.addr_return
        with self.assertLogs(logger, level="WARNING"):
            assert self.tm.pause_task("xyz") is None
        t = self._get_task_mock()
        sync_wait(self.tm.add_new_task(t))
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.pause_task("xyz")
        assert self.tm.tasks["xyz"].task_status == TaskStatus.paused
        assert self.tm.tasks_states["xyz"].status == TaskStatus.paused

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
    def test_get_task_preview(self, _):
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path)
        task_id, _ = self.__build_tasks(tm, 1)

        tm.get_task_preview(task_id)
        assert tm.tasks[task_id].get_preview.called

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_subtasks_borders(self, _):
        count = 3
        tm = TaskManager("ABC", Node(), Mock(), root_path=self.path)
        task_id, _ = self.__build_tasks(tm, count)

        borders = tm.get_subtasks_borders(task_id)
        assert len(borders) == count
        assert all(len(b) == 4 for b in borders.values())

    @patch("golem.task.taskmanager.get_external_address")
    def test_change_timeouts(self, mock_addr):
        mock_addr.return_value = self.addr_return
        t = self._get_task_mock(timeout=20, subtask_timeout=40)
        sync_wait(self.tm.add_new_task(t))
        assert get_timestamp_utc() + 15 <= t.header.deadline
        assert t.header.deadline <= get_timestamp_utc() + 20
        assert t.header.subtask_timeout == 40
        self.tm.change_timeouts("xyz", 60, 10)
        assert get_timestamp_utc() + 55 <= t.header.deadline
        assert t.header.deadline <= get_timestamp_utc() + 60
        assert t.header.subtask_timeout == 10

    @patch("golem.task.taskmanager.get_external_address",
           side_effect=lambda *a, **k: ('1.2.3.4', 40103, None))
    def test_update_signatures(self, _):

        node = Node("node", "key_id", "10.0.0.10", 40103,
                    "1.2.3.4", 40103, None, 40102, 40102)
        task = Task(TaskHeader("node", "task_id", "1.2.3.4", 1234,
                               "key_id", "environment", task_owner=node), '')

        self.tm.keys_auth = EllipticalKeysAuth(self.path)
        sync_wait(self.tm.add_new_task(task))
        sig = task.header.signature

        self.tm.update_task_signatures()
        assert task.header.signature == sig

        task.header.task_owner.pub_port = 40104
        self.tm.update_task_signatures()
        assert task.header.signature != sig

    def test_errors(self):
        task_id = 'qaz123WSX'
        subtask_id = "qweasdzxc"
        t = self._get_task_mock(task_id=task_id, subtask_id=subtask_id)
        sync_wait(self.tm.add_new_task(t))
        with self.assertRaises(RuntimeError):
            sync_wait(self.tm.add_new_task(t))
        with self.assertRaises(TypeError):
            self.tm.set_value(task_id, subtask_id, "incorrect value")
        self.tm.key_id = None
        self.tm.listen_address = "not address"
        self.tm.listen_port = "not a port"
        t = self._get_task_mock(task_id="qaz123WSX2", subtask_id="qweasdzxc")
        with self.assertRaises(ValueError):
            sync_wait(self.tm.add_new_task(t))
        self.tm.key_id = "1"
        with self.assertRaises(IOError):
            sync_wait(self.tm.add_new_task(t))

    def __build_tasks(self, tm, n):
        tm.tasks = dict()
        tm.tasks_states = dict()
        tm.subtask_states = dict()

        task_id = None
        subtask_id = None
        previews = [None, 'result', ['result_1', 'result_2']]

        for i in xrange(0, n):
            task_id = str(uuid.uuid4())

            definition = Mock()
            definition.task_id = task_id
            definition.task_type = "blender"
            definition.subtask_timeout = 3671
            definition.full_task_timeout = 3671 * 10
            definition.max_price = 1 * 10 ** 18
            definition.resolution = [1920, 1080]
            definition.resources = [str(uuid.uuid4()) for _ in range(5)]
            definition.output_file = os.path.join(self.tempdir, 'somefile')
            definition.options.frames = [0]

            subtask_states, subtask_id = self.__build_subtasks(n)

            state = TaskState()
            state.status = 'waiting'
            state.remaining_time = 100 - i
            state.extra_data = dict(result_preview=previews[i % 3])
            state.subtask_states = subtask_states

            task = CoreTask('source.code', definition, 'node', 'blender')
            task.get_total_tasks = Mock()
            task.get_progress = Mock()
            task.get_preview = Mock()
            task.get_total_tasks.return_value = i + 2
            task.get_progress.return_value = i * 10
            task.subtask_states = subtask_states

            tm.tasks[task_id] = task
            tm.tasks_states[task_id] = state
            tm.subtask_states.update(subtask_states)

        tm.subtask2task_mapping = self.__build_subtask2task(tm.tasks)
        return task_id, subtask_id

    @staticmethod
    def __build_subtasks(n):

        subtasks = dict()
        subtask_id = None

        for i in xrange(0, n):

            subtask = SubtaskState()
            subtask.subtask_id = str(uuid.uuid4())
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
        for k, t in tasks.items():
            for sk, st in t.subtask_states.items():
                subtask2task[st.subtask_id] = t.header.task_id
        return subtask2task
