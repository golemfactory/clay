import time
from mock import Mock

from golem.core.common import timeout_to_deadline
from golem.network.p2p.node import Node
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import TaskStatus, SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestTaskManager(LogTestCase, TestDirFixture):
    @staticmethod
    def _get_task_mock(task_id="xyz", subtask_id="xxyyzz", timeout=120, subtask_timeout=120):
        task_mock = Mock()
        task_mock.header.task_id = task_id
        task_mock.header.resource_size = 2 * 1024
        task_mock.header.estimated_memory = 3 * 1024
        task_mock.header.max_price = 10000
        task_mock.header.deadline = timeout_to_deadline(timeout)
        task_mock.query_extra_data.return_value.task_id = task_id
        task_mock.query_extra_data.return_value.subtask_id = subtask_id
        task_mock.query_extra_data.return_value.deadline = timeout_to_deadline(subtask_timeout)
        return task_mock

    def test_get_next_subtask(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        self.assertIsInstance(tm, TaskManager)

        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertEqual(subtask, None)
        self.assertEqual(wrong_task, True)
        task_mock = self._get_task_mock()
        # Task's initial state is set to 'waiting' (found in activeStatus)
        tm.add_new_task(task_mock)
        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertIsNotNone(subtask)
        self.assertEqual(wrong_task, False)
        tm.tasks_states["xyz"].status = tm.activeStatus[0]
        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 1, 10, 2, "10.10.10.10")
        self.assertIsNone(subtask)
        self.assertEqual(wrong_task, False)
        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 2, 2, "10.10.10.10")
        self.assertIsNone(subtask)
        self.assertEqual(wrong_task, False)
        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertIsInstance(subtask, Mock)
        self.assertEqual(wrong_task, False)
        self.assertEqual(tm.tasks_states["xyz"].subtask_states[subtask.subtask_id].computer.price, 10)
        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 20000, 5, 10, 2, "10.10.10.10")
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
        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10,  5, 10, 2, "10.10.10.10")
        self.assertIsInstance(subtask, Mock)
        self.assertEqual(wrong_task, False)
        tm.set_value("xyz", "xxyyzz", 13)
        self.assertEqual(tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 13)
        self.assertEqual(tm.get_value("xxyyzz"), 13)

        tm.set_computation_time("xxyyzz", 12)
        self.assertEqual(tm.tasks_states["xyz"].subtask_states["xxyyzz"].value, 120)

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

    def test_remove_old_tasks(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        tm.remove_old_tasks()
        task_mock = self._get_task_mock()
        tm.add_new_task(task_mock)
        tm.remove_old_tasks()
        assert tm.tasks_states["xyz"].status == TaskStatus.waiting
        task_mock = self._get_task_mock("abc", "aabbcc", 1)
        tm.add_new_task(task_mock)
        time.sleep(1)
        tm.remove_old_tasks()
        assert tm.tasks_states["abc"].status == TaskStatus.timeout
        task_mock = self._get_task_mock("qwe", "qwerty", 10, 1)
        tm.add_new_task(task_mock)
        tm.get_next_subtask("ABC", "ABC", "qwe", 1000, 10, 5, 10, 2, "10.10.10.10")
        time.sleep(1)
        tm.remove_old_tasks()
        assert tm.tasks_states["qwe"].status == TaskStatus.waiting
        assert tm.tasks_states["qwe"].subtask_states["qwerty"].subtask_status == SubtaskStatus.failure
        task_mock = self._get_task_mock("mno", "mmnnoo", 1, 1)
        tm.add_new_task(task_mock)
        tm.get_next_subtask("ABC", "ABC", "mno", 1000, 10, 5, 10, 2, "10.10.10.10")
        time.sleep(1)
        tm.remove_old_tasks()
        assert tm.tasks_states["mno"].status == TaskStatus.timeout
        assert tm.tasks_states["mno"].subtask_states["mmnnoo"].subtask_status == SubtaskStatus.failure
