import os
import time

from mock import MagicMock

from golem.task.taskbase import ComputeTaskDef
from golem.task.taskcomputer import TaskComputer, PyTaskThread, logger
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class TestTaskComputer(TestDirFixture, LogTestCase):
    def test_init(self):
        task_server = MagicMock()
        task_server.get_task_computer_root.return_value = self.path
        tc = TaskComputer("ABC", task_server)
        self.assertIsInstance(tc, TaskComputer)

    def test_run(self):
        task_server = MagicMock()
        task_server.config_desc.task_request_interval = 0.5
        task_server.config_desc.use_waiting_for_task_timeout = True
        task_server.config_desc.waiting_for_task_timeout = 1
        task_server.config_desc.accept_tasks = True
        task_server.get_task_computer_root.return_value = self.path
        tc = TaskComputer("ABC", task_server)
        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.waiting_for_task)
        tc.last_task_request = 0
        tc.run()
        task_server.request_task.assert_called_with()
        task_server.request_task = MagicMock()
        task_server.config_desc.accept_tasks = False
        tc2 = TaskComputer("DEF", task_server)
        tc2.counting_task = False
        tc2.current_computations = []
        tc2.waiting_for_task = None
        tc2.last_task_request = 0

        tc2.run()
        task_server.request_task.assert_not_called()

    def test_computation(self):
        task_server = MagicMock()
        task_server.get_task_computer_root.return_value = self.path
        tc = TaskComputer("ABC", task_server)

        ctd = ComputeTaskDef()
        ctd.task_id = "xyz"
        ctd.subtask_id = "xxyyzz"
        ctd.return_address = "10.10.10.10"
        ctd.return_port = 10203
        ctd.key_id = "key"
        ctd.task_owner = "owner"
        ctd.src_code = "cnt=0\nfor i in range(10000):\n\tcnt += 1\noutput={'data': cnt, 'result_type': 0}"
        ctd.extra_data = {}
        ctd.short_description = "add cnt"
        self.assertEqual(len(tc.assigned_subtasks), 0)
        tc.task_given(ctd, 10)
        self.assertEqual(tc.assigned_subtasks["xxyyzz"], ctd)
        self.assertEqual(tc.assigned_subtasks["xxyyzz"].timeout, 10)
        self.assertEqual(tc.task_to_subtask_mapping["xyz"], "xxyyzz")
        tc.task_server.request_resource.assert_called_with("xyz",  tc.resource_manager.get_resource_header("xyz"),
                                                           "10.10.10.10", 10203, "key", "owner")
        assert tc.task_resource_collected("xyz")
        tc.task_server.unpack_delta.assert_called_with(tc.dir_manager.get_task_resource_dir("xyz"), None, "xyz")
        assert len(tc.current_computations) == 0
        assert tc.assigned_subtasks.get("xxyyzz") is None
        task_server.send_task_failed.assert_called_with("xxyyzz", "xyz", "Host direct task not supported",
                                                        "10.10.10.10", 10203, "key", "owner", "ABC")

        tc.support_direct_computation = True
        tc.task_given(ctd, 10)
        assert tc.task_resource_collected("xyz")
        assert tc.waiting_for_task is None
        assert len(tc.current_computations) ==  1
        self.__wait_for_tasks(tc)

        prev_task_failed_count = task_server.send_task_failed.call_count
        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.assigned_subtasks.get("xxyyzz"))
        assert task_server.send_task_failed.call_count == prev_task_failed_count
        self.assertTrue(task_server.send_results.called)
        args = task_server.send_results.call_args[0]
        self.assertEqual(args[0], "xxyyzz")
        self.assertEqual(args[1], "xyz")
        self.assertEqual(args[2]["data"], 10000)
        self.assertGreater(args[3], 0)
        self.assertLess(args[3], 10)
        self.assertEqual(args[4], "10.10.10.10")
        self.assertEqual(args[5], 10203)
        self.assertEqual(args[6], "key")
        self.assertEqual(args[7], "owner")
        self.assertEqual(args[8], "ABC")

        ctd.subtask_id = "aabbcc"
        ctd.src_code = "raise Exception('some exception')"
        tc.task_given(ctd, 5)
        self.assertEqual(tc.assigned_subtasks["aabbcc"], ctd)
        self.assertEqual(tc.assigned_subtasks["aabbcc"].timeout, 5)
        self.assertEqual(tc.task_to_subtask_mapping["xyz"], "aabbcc")
        tc.task_server.request_resource.assert_called_with("xyz",  tc.resource_manager.get_resource_header("xyz"),
                                                           "10.10.10.10", 10203, "key", "owner")
        self.assertTrue(tc.task_resource_collected("xyz"))
        self.__wait_for_tasks(tc)

        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.assigned_subtasks.get("aabbcc"))
        task_server.send_task_failed.assert_called_with("aabbcc", "xyz", 'some exception', "10.10.10.10",
                                                        10203, "key", "owner", "ABC")

        ctd.subtask_id = "aabbcc2"
        ctd.src_code = "print 'Hello world'"
        tc.task_given(ctd, 5)
        self.assertTrue(tc.task_resource_collected("xyz"))
        self.__wait_for_tasks(tc)

        task_server.send_task_failed.assert_called_with("aabbcc2", "xyz", "Wrong result format", "10.10.10.10", 10203,
                                                        "key", "owner", "ABC")

        ctd.subtask_id = "xxyyzz2"
        tc.task_given(ctd, 1)
        self.assertTrue(tc.task_resource_collected("xyz"))
        tt = tc.current_computations[0]
        tc.task_computed(tc.current_computations[0])
        self.assertEqual(len(tc.current_computations), 0)
        task_server.send_task_failed.assert_called_with("xxyyzz2", "xyz", "Wrong result format", "10.10.10.10", 10203,
                                                        "key", "owner", "ABC")
        tt.end_comp()
        time.sleep(0.5)

    @staticmethod
    def __wait_for_tasks(tc):
        [t.join() for t in tc.current_computations]


class TestTaskThread(TestDirFixture):
    def test_thread(self):
        files_ = self.additional_dir_content([0, [1], [1], [1], [1]])
        tc = TaskComputer("ABC", MagicMock())
        tc.counting_task = True
        tt = PyTaskThread(tc, "xxyyzz", self.path, "cnt=0\nfor i in range(1000000):\n\tcnt += 1\noutput=cnt", {},
                          "hello thread", os.path.dirname(files_[0]), os.path.dirname(files_[1]), 20)
        tt.run()
        self.assertGreater(tt.end_time - tt.start_time, 0)
        self.assertLess(tt.end_time - tt.start_time, 20)
        self.assertFalse(tc.counting_task)
