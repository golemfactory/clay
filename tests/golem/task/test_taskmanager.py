from mock import Mock

from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskHeader, ComputeTaskDef
from golem.task.taskmanager import TaskManager, logger
from golem.task.taskstate import SubtaskStatus, TaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestTaskManager(LogTestCase, TestDirFixture):

    def test_get_next_subtask(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        self.assertIsInstance(tm, TaskManager)

        subtask, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")
        self.assertEqual(subtask, None)
        self.assertEqual(wrong_task, True)
        task_mock = Mock()
        task_mock.header.task_id = "xyz"
        task_mock.header.resource_size = 2 * 1024
        task_mock.header.estimated_memory = 3 * 1024
        task_mock.header.max_price = 10000
        task_mock.query_extra_data.return_value.task_id = "xyz"
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
        task_mock = Mock()
        task_mock.header.task_id = "xyz"
        task_mock.header.resource_size = 2 * 1024
        task_mock.header.estimated_memory = 3 * 1024
        task_mock.header.max_price = 1000
        task_mock.query_extra_data.return_value.task_id = "xyz"
        task_mock.query_extra_data.return_value.subtask_id = "xxyyzz"
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
        hash_resources = [['first', 'deadbeef01'], ['second', 'deadbeef02']]

        def get_resources(*args):
            return resources

        task_mock = Mock()
        task_mock.header.task_id = task_id
        task_mock.header.resource_size = 2 * 1024
        task_mock.header.estimated_memory = 3 * 1024
        task_mock.header.max_price = 10000
        task_mock.get_resources = get_resources
        task_mock.query_extra_data.return_value.task_id = task_id

        tm.add_new_task(task_mock)

        assert tm.get_resources(task_id, task_mock.header) is resources
        assert not tm.get_resources(task_id + "2", task_mock.header)

    def test_computed_task_received(self):
        tm = TaskManager("ABC", Node(), root_path=self.path)
        th = TaskHeader("ABC", "xyz", "10.10.10.10", 1024, "key_id", "DEFAULT")
        th.max_price = 50

        class TestTask(Task):
            def __init__(self, header, src_code, subtasks_id):
                super(TestTask, self).__init__(header, src_code)
                self.finished = {k: False for k in subtasks_id}
                self.restarted = {k: False for k in subtasks_id}
                self.subtasks_id = subtasks_id

            def query_extra_data(self, perf_index, num_cores=1, node_id=None, node_name=None):
                ctd = ComputeTaskDef()
                ctd.task_id = self.header.task_id
                ctd.subtask_id = self.subtasks_id[0]
                self.subtasks_id = self.subtasks_id[1:]
                return ctd

            def needs_computation(self):
                return sum(self.finished.values()) != len(self.finished)

            def computation_finished(self, subtask_id, task_result, dir_manager=None, result_type=0):
                if not self.restarted[subtask_id]:
                    self.finished[subtask_id] = True

            def verify_subtask(self, subtask_id):
                return self.finished[subtask_id]

            def finished_computation(self):
                return not self.needs_computation()

            def verify_task(self):
                return self.finished_computation()

            def restart_subtask(self, subtask_id):
                self.restarted[subtask_id] = True

        t = TestTask(th, "print 'Hello world'", ["xxyyzz"])
        tm.add_new_task(t)
        ctd, wrong_task = tm.get_next_subtask("DEF", "DEF", "xyz", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "xxyyzz"
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

        t2 = TestTask(th, "print 'Hello world'", ["aabbcc"])
        tm.add_new_task(t2)
        ctd, wrong_task = tm.get_next_subtask("DEF", "DEF", "abc", 1030, 10, 10000, 10000, 10000)
        assert not wrong_task
        assert ctd.subtask_id == "aabbcc"
        tm.restart_subtask("aabbcc")
        ss = tm.tasks_states["abc"].subtask_states["aabbcc"]
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not tm.computed_task_received("aabbcc", [], 0)
        assert ss.subtask_progress == 0.0
        assert ss.subtask_status == SubtaskStatus.restarted
        assert not t2.finished["aabbcc"]
        t2.restarted["aabbcc"] = False
        assert tm.computed_task_received("aabbcc", [], 0)
        assert ss.subtask_progress == 0.0
        assert ss.subtask_status == SubtaskStatus.restarted
        assert t2.finished

        th.task_id = "qwe"
        t3 = TestTask(th, "print 'Hello world!", ["qqwwee", "rrttyy"])
        tm.add_new_task(t3)
        ctd, wrong_task = tm.get_next_subtask("DEF", "DEF", "qwe", 1030, 10, 10000, 10000, 10000)
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





