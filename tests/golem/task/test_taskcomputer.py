import mock
import os
import random
import time

from golem.client import ClientTaskComputerEventListener
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline
from golem.task.taskbase import ComputeTaskDef
from golem.task.taskcomputer import TaskComputer, PyTaskThread
from golem.tools.ci import ci_skip
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


@ci_skip
class TestTaskComputer(TestDirFixture, LogTestCase):
    def test_init(self):
        task_server = mock.MagicMock()
        task_server.get_task_computer_root.return_value = self.path
        task_server.config_desc = config_desc()
        tc = TaskComputer("ABC", task_server, use_docker_machine_manager=False)
        self.assertIsInstance(tc, TaskComputer)

    def test_run(self):
        task_server = mock.MagicMock()
        task_server.config_desc = config_desc()
        task_server.config_desc.task_request_interval = 0.5
        task_server.config_desc.use_waiting_for_task_timeout = True
        task_server.config_desc.waiting_for_task_timeout = 1
        task_server.config_desc.accept_tasks = True
        task_server.get_task_computer_root.return_value = self.path
        tc = TaskComputer("ABC", task_server, use_docker_machine_manager=False)
        self.assertFalse(tc.counting_task)
        self.assertEqual(len(tc.current_computations), 0)
        self.assertIsNone(tc.waiting_for_task)
        tc.last_task_request = 0
        tc.run()
        task_server.request_task.assert_called_with()
        task_server.request_task = mock.MagicMock()
        task_server.config_desc.accept_tasks = False
        tc2 = TaskComputer("DEF", task_server, use_docker_machine_manager=False)
        tc2.counting_task = False
        tc2.current_computations = []
        tc2.waiting_for_task = None
        tc2.last_task_request = 0

        tc2.run()
        task_server.request_task.assert_not_called()

        tc2.runnable = True
        tc2.compute_tasks = True
        tc2.waiting_for_task = False
        tc2.counting_task = False

        tc2.last_task_request = 0
        tc2.current_computations = []

        tc2.run()

        assert task_server.request_task.called

        task_server.request_task.called = False

        tc2.waiting_for_task = 'xxyyzz'
        tc2.use_waiting_ttl = True
        tc2.last_checking = 10 ** 10

        tc2.run()
        tc2.session_timeout()

    def test_resource_failure(self):
        task_server = mock.MagicMock()
        task_server.config_desc = config_desc()
        tc = TaskComputer("ABC", task_server, use_docker_machine_manager=False)

        task_id = 'xyz'
        subtask_id = 'xxyyzz'

        tc.task_resource_failure(task_id, 'reason')
        assert not task_server.send_task_failed.called

        tc.task_to_subtask_mapping[task_id] = subtask_id
        tc.assigned_subtasks[subtask_id] = mock.Mock()

        tc.task_resource_failure(task_id, 'reason')
        assert task_server.send_task_failed.called

        tc.resource_request_rejected(subtask_id, 'reason')

    def test_computation(self):
        task_server = mock.MagicMock()
        task_server.get_task_computer_root.return_value = self.path
        task_server.config_desc = config_desc()
        tc = TaskComputer("ABC", task_server, use_docker_machine_manager=False)

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
        ctd.deadline = timeout_to_deadline(10)
        self.assertEqual(len(tc.assigned_subtasks), 0)
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtasks["xxyyzz"], ctd)
        self.assertLessEqual(tc.assigned_subtasks["xxyyzz"].deadline, timeout_to_deadline(10))
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
        tc.task_given(ctd)
        assert tc.task_resource_collected("xyz")
        assert not tc.waiting_for_task
        assert len(tc.current_computations) == 1
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
        ctd.deadline = timeout_to_deadline(5)
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtasks["aabbcc"], ctd)
        self.assertLessEqual(tc.assigned_subtasks["aabbcc"].deadline, timeout_to_deadline(5))
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
        ctd.timeout = timeout_to_deadline(5)
        tc.task_given(ctd)
        self.assertTrue(tc.task_resource_collected("xyz"))
        self.__wait_for_tasks(tc)

        task_server.send_task_failed.assert_called_with("aabbcc2", "xyz", "Wrong result format", "10.10.10.10", 10203,
                                                        "key", "owner", "ABC")

        ctd.subtask_id = "xxyyzz2"
        ctd.timeout = timeout_to_deadline(1)
        tc.task_given(ctd)
        self.assertTrue(tc.task_resource_collected("xyz"))
        tt = tc.current_computations[0]
        tc.task_computed(tc.current_computations[0])
        self.assertEqual(len(tc.current_computations), 0)
        task_server.send_task_failed.assert_called_with("xxyyzz2", "xyz", "Wrong result format", "10.10.10.10", 10203,
                                                        "key", "owner", "ABC")
        tt.end_comp()
        time.sleep(0.5)
        if tt.is_alive():
            tt.join(timeout=5)

    def test_change_config(self):
        task_server = mock.MagicMock()
        task_server.config_desc = config_desc()

        tc = TaskComputer("ABC", task_server, use_docker_machine_manager=False)
        tc.docker_manager = mock.Mock()

        tc.use_docker_machine_manager = False
        tc.change_config(mock.Mock(), in_background=False)
        assert not tc.docker_manager.update_config.called

        tc.use_docker_machine_manager = True
        tc.docker_manager.update_config = lambda x, y, z: x()

        tc.counting_task = True
        tc.change_config(mock.Mock(), in_background=False)

        tc.docker_manager.update_config = lambda x, y, z: y()

        tc.counting_task = False
        tc.change_config(mock.Mock(), in_background=False)

    def test_event_listeners(self):
        client = mock.Mock()
        task_server = mock.MagicMock()
        task_server.config_desc = config_desc()
        tc = TaskComputer("ABC", task_server, use_docker_machine_manager=False)

        tc.lock_config(True)
        tc.lock_config(False)

        listener = ClientTaskComputerEventListener(client)
        tc.register_listener(listener)

        tc.lock_config(True)
        client.lock_config.assert_called_with(True)

        tc.lock_config(False)
        client.lock_config.assert_called_with(False)

    @staticmethod
    def __wait_for_tasks(tc):
        [t.join() for t in tc.current_computations]


@ci_skip
class TestTaskThread(TestDirFixture):
    def test_thread(self):
        files_ = self.additional_dir_content([0, [1], [1], [1], [1]])
        ts = mock.MagicMock()
        ts.config_desc = config_desc()
        tc = TaskComputer("ABC", ts, use_docker_machine_manager=False)
        tc.counting_task = True
        tc.waiting_for_task = None
        tt = PyTaskThread(tc, "xxyyzz", self.path, "cnt=0\nfor i in range(1000000):\n\tcnt += 1\noutput=cnt", {},
                          "hello thread", os.path.dirname(files_[0]), os.path.dirname(files_[1]), 20)
        tt.run()
        self.assertGreater(tt.end_time - tt.start_time, 0)
        self.assertLess(tt.end_time - tt.start_time, 20)
        self.assertTrue(tc.counting_task)


class TestTaskMonitor(TestDirFixture):
    def test_task_computed(self):
        """golem.monitor signal"""
        from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
        from golem.monitor.monitor import SystemMonitor
        from golem.monitorconfig import MONITOR_CONFIG
        monitor = SystemMonitor(NodeMetadataModel("CLIID", "SESSID", "hackix", "3.1337", "Descr", config_desc()), MONITOR_CONFIG)
        task_server = mock.MagicMock()
        task_server.config_desc = config_desc()
        task = TaskComputer("ABC", task_server, use_docker_machine_manager=False)

        task_thread = mock.MagicMock()
        task_thread.start_time = time.time()
        duration = random.randint(1, 100)
        task_thread.end_time = task_thread.start_time + duration

        def prepare():
            subtask = mock.MagicMock()
            subtask_id = random.randint(3000, 4000)
            task.assigned_subtasks[subtask_id] = subtask
            task_thread.subtask_id = subtask_id

        def check(expected):
            with mock.patch('golem.monitor.monitor.SenderThread.send') as mock_send:
                task.task_computed(task_thread)
                self.assertEquals(mock_send.call_count, 1)
                result = mock_send.call_args[0][0].dict_repr()
                for key in ('cliid', 'sessid', 'timestamp'):
                    del result[key]
                expected_d = {
                    'type': 'ComputationTime',
                    'success': expected,
                    'value': duration,
                }
                self.assertEquals(expected_d, result)

        # error case
        prepare()
        task_thread.error = True
        check(False)

        # success case
        prepare()
        task_thread.error = False
        task_thread.error_msg = None
        task_thread.result = {'data': 'oh senora!!!', 'result_type': 'Cadencia da Vila'}
        check(True)

        # default case (error)
        prepare()
        task_thread.result = None
        check(False)


def config_desc():
    ccd = ClientConfigDescriptor()
    ccd.estimated_blender_performance = 2000.0
    ccd.estimated_lux_performance = 2000.0
    return ccd
