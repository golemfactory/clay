import time

from mock import Mock, patch

from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskHeader, ComputeTaskDef, TaskEventListener
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import SubtaskStatus, SubtaskState, TaskState, TaskStatus

from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestTaskManager(LogTestCase, TestDirFixture):
    def setUp(self):
        super(TestTaskManager, self).setUp()
        self.tm = TaskManager("ABC", Node(), root_path=self.path)
        self.tm.key_id = "KEYID"
        self.tm.listen_address = "10.10.10.10"
        self.tm.listen_port = 2222
        self.addr_return = ("10.10.10.10", 1111, "Full NAT")

    @staticmethod
    def _get_task_mock(task_id="xyz", subtask_id="xxyyzz"):
        task_mock = Mock()
        task_mock.header.task_id = task_id
        task_mock.header.resource_size = 2 * 1024
        task_mock.header.estimated_memory = 3 * 1024
        task_mock.header.max_price = 10000
        ctd = ComputeTaskDef()
        ctd.task_id = task_id
        ctd.subtask_id = subtask_id
        ctd.environment = "DEFAULT"
        task_mock.query_extra_data.return_value.ctd = ctd
        task_mock.get_progress.return_value = 0.3
        return task_mock

    @patch("golem.task.taskmanager.get_external_address")
    def test_get_next_subtask(self, mock_addr):
        mock_addr.return_value = self.addr_return
        assert isinstance(self.tm, TaskManager)

        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert subtask is None
        assert wrong_task

        task_mock = self._get_task_mock()

        # Task's initial state is set to 'waiting' (found in activeStatus)
        self.tm.add_new_task(task_mock)
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

        task_mock.query_extra_data.return_value.ctd.subtask_id = "xyzxyz"
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert isinstance(subtask, ComputeTaskDef)
        assert not wrong_task
        assert self.tm.tasks_states["xyz"].subtask_states[subtask.subtask_id].computer.price == 10

        task_mock.query_extra_data.return_value.ctd.subtask_id = "xyzxyz2"
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

        task_mock.query_extra_data.return_value.ctd.subtask_id = None
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

        self.tm.add_new_task(task_mock)
        with self.assertLogs(logger, level="WARNING") as l:
            self.tm.set_value("xyz", "xxyyzz", 13)
        assert any("not my subtask" in log for log in l.output)

        self.tm.tasks_states["xyz"].status = self.tm.activeStatus[0]
        subtask, wrong_task, wait = self.tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10,  5, 10, 2, "10.10.10.10")
        self.assertIsInstance(subtask, ComputeTaskDef)
        self.assertEqual(wrong_task, False)

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

        def get_resources(*args):
            return resources

        task_mock = self._get_task_mock()
        task_mock.get_resources = get_resources

        self.tm.add_new_task(task_mock)

        assert self.tm.get_resources(task_id, task_mock.header) is resources
        assert not self.tm.get_resources(task_id + "2", task_mock.header)

    @patch("golem.task.taskmanager.get_external_address")
    def test_computed_task_received(self, mock_addr):
        mock_addr.return_value = self.addr_return
        self.tm.listeners.append(Mock())
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
        self.tm.add_new_task(t)
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
        self.tm.add_new_task(t2)
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
        self.tm.add_new_task(t3)
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
        self.tm.add_new_task(t2)
        ctd, wrong_task, should_wait = self.tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2,
                                                           "10.10.10.10")
        assert not wrong_task
        assert ctd.subtask_id == "ttt4"
        assert not self.tm.computed_task_received("ttt4", [], 0)
        self.tm.listeners[0].task_status_updated.assert_called_with("task4")
        assert self.tm.tasks_states["task4"].subtask_states["ttt4"].subtask_status == SubtaskStatus.failure
        prev_call = self.tm.listeners[0].task_status_updated.call_count
        assert not self.tm.computed_task_received("ttt4", [], 0)
        assert self.tm.listeners[0].task_status_updated.call_count == prev_call + 1
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

        self.tm.task_result_incoming(subtask_id)
        assert not task_mock.result_incoming.called

        task_mock.subtasks_given = dict()
        task_mock.subtasks_given[subtask_id] = TaskClient(node_id)

        subtask_state = SubtaskState()
        subtask_state.status = SubtaskStatus.waiting
        subtask_state.subtask_id = subtask_id
        subtask_state.computer = Mock()
        subtask_state.computer.node_id = node_id

        task_state = TaskState()
        task_state.computer = Mock()
        task_state.subtask_states[subtask_id] = subtask_state

        self.tm.add_new_task(task_mock)
        self.tm.subtask2task_mapping[subtask_id] = "xyz"
        self.tm.tasks_states["xyz"] = task_state

        self.tm.task_result_incoming(subtask_id)
        assert task_mock.result_incoming.called

        task_mock.result_incoming.called = False
        self.tm.tasks = []

        self.tm.task_result_incoming(subtask_id)
        assert not task_mock.result_incoming.called

    @patch("golem.task.taskmanager.get_external_address")
    def test_get_subtasks(self, mock_addr):
        mock_addr.return_value = self.addr_return
        assert self.tm.get_subtasks("Task 1") is None
        task_mock = self._get_task_mock()
        self.tm.add_new_task(task_mock)
        task_mock2 = self._get_task_mock("TASK 1", "SUBTASK 1")
        self.tm.add_new_task(task_mock2)
        assert self.tm.get_subtasks("xyz") == []
        assert self.tm.get_subtasks("TASK 1") == []
        self.tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        self.tm.get_next_subtask("NODEID", "NODENAME", "TASK 1", 1000, 100, 10000, 10000)
        task_mock.query_extra_data.return_value.ctd.subtask_id = "aabbcc"
        self.tm.get_next_subtask("NODEID2", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        task_mock.query_extra_data.return_value.ctd.subtask_id = "ddeeff"
        self.tm.get_next_subtask("NODEID3", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        assert set(self.tm.get_subtasks("xyz")) == {"xxyyzz", "aabbcc", "ddeeff"}
        assert self.tm.get_subtasks("TASK 1") == ["SUBTASK 1"]

    @patch("golem.task.taskmanager.get_external_address")
    def test_resource_send(self, mock_addr):
        mock_addr.return_value = self.addr_return
        self.tm.listeners.append(Mock())
        t = Task(TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "abcde",
                            "DEFAULT"), "print 'hello world'")
        self.tm.add_new_task(t)
        self.tm.resources_send("xyz")
        assert self.tm.listeners[0].notice_task_updated.called_with("xyz")

    @patch("golem.task.taskmanager.get_external_address")
    def test_remove_old_tasks(self, mock_addr):
        mock_addr.return_value = self.addr_return
        self.tm.listeners.append(Mock())
        t = Task(Mock(), "")
        t.header.task_id = "xyz"
        t.header.ttl = 0.5
        t.header.last_checking = time.time()
        self.tm.add_new_task(t)
        assert self.tm.tasks_states["xyz"].status in self.tm.activeStatus
        time.sleep(1)
        self.tm.remove_old_tasks()
        assert self.tm.tasks.get('xyz') is None

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
        self.tm.add_new_task(t)
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
        self.tm.add_new_task(t)
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
        self.tm.add_new_task(t)
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.restart_task("xyz")
        assert self.tm.tasks["xyz"].task_status == TaskStatus.waiting
        assert self.tm.tasks_states["xyz"].status == TaskStatus.waiting
        self.tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        t.query_extra_data.return_value.ctd.subtask_id = "xxyyzz2"
        self.tm.get_next_subtask("NODEID2", "NODENAME2", "xyz", 1000, 100, 10000, 10000)
        assert len(self.tm.tasks_states["xyz"].subtask_states) == 2
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
        self.tm.add_new_task(t)
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
        self.tm.add_new_task(t)
        with self.assertNoLogs(logger, level="WARNING"):
            self.tm.pause_task("xyz")
        assert self.tm.tasks["xyz"].task_status == TaskStatus.paused
        assert self.tm.tasks_states["xyz"].status == TaskStatus.paused
