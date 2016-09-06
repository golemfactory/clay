import time

from mock import Mock

from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskHeader, ComputeTaskDef, TaskEventListener
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import SubtaskStatus, SubtaskState, TaskState, TaskStatus

from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestTaskManager(LogTestCase, TestDirFixture):
    @staticmethod
    def _get_task_mock(task_id="xyz", subtask_id="xxyyzz"):
        task_mock = Mock()
        task_mock.header.task_id = task_id
        task_mock.header.resource_size = 2 * 1024
        task_mock.header.estimated_memory = 3 * 1024
        task_mock.header.max_price = 10000
        task_mock.query_extra_data.return_value.ctd.task_id = task_id
        task_mock.query_extra_data.return_value.ctd.subtask_id = subtask_id
        return task_mock

    def test_get_next_subtask(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        self.assertIsInstance(tm, TaskManager)

        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertEqual(subtask, None)
        self.assertEqual(wrong_task, True)

        task_mock = self._get_task_mock()

        # Task's initial state is set to 'waiting' (found in activeStatus)
        tm.add_new_task(task_mock)
        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertIsNotNone(subtask)
        self.assertEqual(wrong_task, False)
        tm.tasks_states["xyz"].status = tm.activeStatus[0]
        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 1, 10, 2, "10.10.10.10")
        self.assertIsNone(subtask)
        self.assertEqual(wrong_task, False)
        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 2, 2, "10.10.10.10")
        self.assertIsNone(subtask)
        self.assertEqual(wrong_task, False)
        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertIsInstance(subtask, Mock)
        self.assertEqual(wrong_task, False)
        self.assertEqual(tm.tasks_states["xyz"].subtask_states[subtask.subtask_id].computer.price, 10)
        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 20000, 5, 10, 2, "10.10.10.10")
        self.assertIsNone(subtask)
        self.assertFalse(wrong_task)
        tm.delete_task("xyz")
        assert tm.tasks.get("xyz") is None
        assert tm.tasks_states.get("xyz") is None

    def test_get_and_set_value(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        with self.assertLogs(logger, level=1) as l:
            tm.set_value("xyz", "xxyyzz", 13)
        self.assertTrue(any(["not my task" in log for log in l.output]))
        with self.assertLogs(logger, level=1) as l:
            tm.get_value("xxyyzz")

        with self.assertLogs(logger, level=1) as l:
            tm.set_computation_time("xxyyzz", 12)

        task_mock = self._get_task_mock()

        tm.add_new_task(task_mock)
        with self.assertLogs(logger, level=1) as l:
            tm.set_value("xyz", "xxyyzz", 13)
        self.assertTrue(any(["not my subtask" in log for log in l.output]))

        tm.tasks_states["xyz"].status = tm.activeStatus[0]
        subtask, wrong_task, wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10,  5, 10, 2, "10.10.10.10")
        self.assertIsInstance(subtask, Mock)
        self.assertEqual(wrong_task, False)

        tm.set_value("xyz", "xxyyzz", 13)
        self.assertEqual(tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 13)
        self.assertEqual(tm.get_value("xxyyzz"), 13)

        tm.set_computation_time("xxyyzz", 3601)
        self.assertEqual(tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 11)

    def test_change_config(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        self.assertTrue(tm.use_distributed_resources)
        tm.change_config(self.path, False)
        self.assertFalse(tm.use_distributed_resources)

    def test_get_resources(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        task_id = "xyz"

        resources = ['first', 'second']

        def get_resources(*args):
            return resources

        task_mock = self._get_task_mock()
        task_mock.get_resources = get_resources

        tm.add_new_task(task_mock)

        assert tm.get_resources(task_id, task_mock.header) is resources
        assert not tm.get_resources(task_id + "2", task_mock.header)

    def test_computed_task_received(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        tm.listeners.append(Mock())
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
        tm.add_new_task(t)
        ctd, wrong_task, should_wait = tm.get_next_subtask("DEF", "DEF", "xyz", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "xxyyzz"
        assert not should_wait
        task_id = tm.subtask2task_mapping["xxyyzz"]
        assert task_id == "xyz"
        ss = tm.tasks_states["xyz"].subtask_states["xxyyzz"]
        assert ss.subtask_status == SubtaskStatus.starting
        assert tm.computed_task_received("xxyyzz", [], 0)
        assert t.finished["xxyyzz"]
        assert ss.subtask_progress == 1.0
        assert ss.subtask_rem_time == 0.0
        assert ss.subtask_status == SubtaskStatus.finished
        assert tm.tasks_states["xyz"].status == TaskStatus.finished

        th.task_id = "abc"
        t2 = TestTask(th, "print 'Hello world'", ["aabbcc"], verify_subtasks={"aabbcc": True})
        tm.add_new_task(t2)
        ctd, wrong_task, should_wait = tm.get_next_subtask("DEF", "DEF", "abc", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "aabbcc"
        assert not should_wait
        tm.restart_subtask("aabbcc")
        ss = tm.tasks_states["abc"].subtask_states["aabbcc"]
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not tm.computed_task_received("aabbcc", [], 0)
        assert ss.subtask_progress == 0.0
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not t2.finished["aabbcc"]


        th.task_id = "qwe"
        t3 = TestTask(th, "print 'Hello world!", ["qqwwee", "rrttyy"], {"qqwwee": True, "rrttyy": True})
        tm.add_new_task(t3)
        ctd, wrong_task, should_wait = tm.get_next_subtask("DEF", "DEF", "qwe", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "qqwwee"
        tm.task_computation_failure("qqwwee", "something went wrong")
        ss = tm.tasks_states["qwe"].subtask_states["qqwwee"]
        assert ss.subtask_status == SubtaskStatus.failure
        assert ss.subtask_progress == 1.0
        assert ss.subtask_rem_time == 0.0
        assert ss.stderr == "something went wrong"
        with self.assertLogs(logger, level="WARNING"):
            assert not tm.computed_task_received("qqwwee", [], 0)

        th.task_id = "task4"
        t2 = TestTask(th, "print 'Hello world!", ["ttt4", "sss4"], {'ttt4': False, 'sss4': True})
        tm.add_new_task(t2)
        ctd, wrong_task, should_wait = tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2,
                                                           "10.10.10.10")
        assert not wrong_task
        assert ctd.subtask_id == "ttt4"
        assert not tm.computed_task_received("ttt4", [], 0)
        tm.listeners[0].task_status_updated.assert_called_with("task4")
        assert tm.tasks_states["task4"].subtask_states["ttt4"].subtask_status == SubtaskStatus.failure
        prev_call = tm.listeners[0].task_status_updated.call_count
        assert not tm.computed_task_received("ttt4", [], 0)
        assert tm.listeners[0].task_status_updated.call_count == prev_call + 1
        ctd, wrong_task, should_wait = tm.get_next_subtask("DEF", "DEF", "task4", 1000, 10, 5, 10, 2, "10.10.10.10")
        assert not wrong_task
        assert ctd.subtask_id == "sss4"
        assert tm.computed_task_received("sss4", [], 0)

    def test_task_result_incoming(self):
        subtask_id = "xxyyzz"
        node_id = 'node'

        tm = TaskManager("ABC", Node(), root_path=self.path)

        task_mock = self._get_task_mock()
        task_mock.counting_nodes = {}

        tm.task_result_incoming(subtask_id)
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

        tm.add_new_task(task_mock)
        tm.subtask2task_mapping[subtask_id] = "xyz"
        tm.tasks_states["xyz"] = task_state

        tm.task_result_incoming(subtask_id)
        assert task_mock.result_incoming.called

        task_mock.result_incoming.called = False
        tm.tasks = []

        tm.task_result_incoming(subtask_id)
        assert not task_mock.result_incoming.called

    def test_get_subtasks(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        assert tm.get_subtasks("Task 1") is None
        task_mock = self._get_task_mock()
        tm.add_new_task(task_mock)
        task_mock2 = self._get_task_mock("TASK 1", "SUBTASK 1")
        tm.add_new_task(task_mock2)
        assert tm.get_subtasks("xyz") == []
        assert tm.get_subtasks("TASK 1") == []
        tm.get_next_subtask("NODEID", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        tm.get_next_subtask("NODEID", "NODENAME", "TASK 1", 1000, 100, 10000, 10000)
        task_mock.query_extra_data.return_value.ctd.subtask_id = "aabbcc"
        tm.get_next_subtask("NODEID2", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        task_mock.query_extra_data.return_value.ctd.subtask_id = "ddeeff"
        tm.get_next_subtask("NODEID3", "NODENAME", "xyz", 1000, 100, 10000, 10000)
        assert set(tm.get_subtasks("xyz")) == {"xxyyzz", "aabbcc", "ddeeff"}
        assert tm.get_subtasks("TASK 1") == ["SUBTASK 1"]

    def test_resource_send(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        tm.listeners.append(Mock())
        t = Task(TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "abcde",
                            "DEFAULT"), "print 'hello world'")
        tm.add_new_task(t)
        tm.resources_send("xyz")
        assert tm.listeners[0].notice_task_updated.called_with("xyz")

    def test_remove_old_tasks(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        tm.listeners.append(Mock())
        t = Task(Mock(), "")
        t.header.task_id = "xyz"
        t.header.ttl = 0.5
        t.header.last_checking = time.time()
        tm.add_new_task(t)
        assert tm.tasks_states["xyz"].status in tm.activeStatus
        time.sleep(1)
        tm.remove_old_tasks()
        assert tm.tasks.get('xyz') is None

    def test_task_event_listener(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        tm.notice_task_updated = Mock()
        assert isinstance(tm, TaskEventListener)
        tm.notify_update_task("xyz")
        tm.notice_task_updated.assert_called_with("xyz")
