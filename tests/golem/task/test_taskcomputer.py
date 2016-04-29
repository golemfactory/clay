import os
import time

from mock import MagicMock

from golem.task.taskbase import ComputeTaskDef
from golem.task.taskcomputer import TaskComputer, PyTaskThread
from golem.tools.testdirfixture import TestDirFixture


class TestTaskComputer(TestDirFixture):
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
        task_server.get_task_computer_root.return_value = self.path
        tc = TaskComputer("ABC", task_server)
        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.waiting_for_task)
        tc.run()
        time.sleep(1)
        tc.run()
        task_server.request_task.assert_called_with()

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
        ctd.timeout = 10
        self.assertEqual(len(tc.assigned_subtasks), 0)
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtasks["xxyyzz"], ctd)
        self.assertEqual(tc.assigned_subtasks["xxyyzz"].timeout, 10)
        self.assertEqual(tc.task_to_subtask_mapping["xyz"], "xxyyzz")
        tc.task_server.request_resource.assert_called_with("xyz",  tc.resource_manager.get_resource_header("xyz"),
                                                           "10.10.10.10", 10203, "key", "owner")
        self.assertTrue(tc.task_resource_collected("xyz"))
        tc.task_server.unpack_delta.assert_called_with(tc.dir_manager.get_task_resource_dir("xyz"), None, "xyz")
        self.assertIsNone(tc.waiting_for_task)
        self.assertEqual(len(tc.current_computations), 1)
        time.sleep(0.5)
        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.assigned_subtasks.get("xxyyzz"))
        task_server.send_task_failed.assert_not_called()
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
        ctd.timeout = 5
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtasks["aabbcc"], ctd)
        self.assertEqual(tc.assigned_subtasks["aabbcc"].timeout, 5)
        self.assertEqual(tc.task_to_subtask_mapping["xyz"], "aabbcc")
        tc.task_server.request_resource.assert_called_with("xyz",  tc.resource_manager.get_resource_header("xyz"),
                                                           "10.10.10.10", 10203, "key", "owner")
        self.assertTrue(tc.task_resource_collected("xyz"))
        time.sleep(0.5)
        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.assigned_subtasks.get("aabbcc"))
        task_server.send_task_failed.assert_called_with("aabbcc", "xyz", 'some exception', "10.10.10.10",
                                                        10203, "key", "owner", "ABC")

        ctd.subtask_id = "aabbcc2"
        ctd.src_code = "print 'Hello world'"
        ctd.timeout = 5
        tc.task_given(ctd)
        self.assertTrue(tc.task_resource_collected("xyz"))
        time.sleep(0.5)
        task_server.send_task_failed.assert_called_with("aabbcc2", "xyz", "Wrong result format", "10.10.10.10", 10203,
                                                        "key", "owner", "ABC")

        ctd.subtask_id = "xxyyzz2"
        ctd.timeout = 1
        tc.task_given(ctd)
        self.assertTrue(tc.task_resource_collected("xyz"))
        tt = tc.current_computations[0]
        tc.task_computed(tc.current_computations[0])
        self.assertEqual(len(tc.current_computations), 0)
        task_server.send_task_failed.assert_called_with("xxyyzz2", "xyz", "Wrong result format", "10.10.10.10", 10203,
                                                        "key", "owner", "ABC")
        tt.end_comp()
        time.sleep(0.5)


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
