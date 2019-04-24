import os
import random
from threading import Lock
import time
import unittest.mock as mock
import uuid

from golem_messages.message import ComputeTaskDef

from golem.client import ClientTaskComputerEventListener
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline
from golem.core.deferred import sync_wait
from golem.docker.manager import DockerManager
from golem.task.taskcomputer import TaskComputer, PyTaskThread
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip
from golem.tools.assertlogs import LogTestCase
from golem.tools.os_info import OSInfo


@ci_skip
class TestTaskComputer(DatabaseFixture, LogTestCase):

    def setUp(self):
        super(TestTaskComputer, self).setUp()
        task_server = mock.MagicMock()
        task_server.benchmark_manager.benchmarks_needed.return_value = False
        task_server.get_task_computer_root.return_value = self.path
        task_server.config_desc = ClientConfigDescriptor()

        self.task_server = task_server

    def test_init(self):
        task_server = self.task_server
        tc = TaskComputer(task_server, use_docker_manager=False)
        self.assertIsInstance(tc, TaskComputer)

    def test_run(self):
        task_server = self.task_server
        task_server.config_desc.task_request_interval = 0.5
        task_server.config_desc.accept_tasks = True
        task_server.get_task_computer_root.return_value = self.path
        tc = TaskComputer(task_server, use_docker_manager=False)
        self.assertIsNone(tc.counting_thread)
        tc.last_task_request = 0
        tc.run()
        task_server.request_task.assert_called_with()
        task_server.request_task = mock.MagicMock()
        task_server.config_desc.accept_tasks = False
        tc2 = TaskComputer(task_server, use_docker_manager=False)
        tc2.counting_thread = None
        tc2.last_task_request = 0

        tc2.run()
        task_server.request_task.assert_not_called()

        tc2.runnable = True
        tc2.compute_tasks = True

        tc2.last_task_request = 0
        tc2.counting_thread = None

        tc2.run()

        assert task_server.request_task.called

        task_server.request_task.called = False

        tc2.last_checking = 10 ** 10

        tc2.run()

    def test_resource_failure(self):
        task_server = self.task_server

        tc = TaskComputer(task_server, use_docker_manager=False)

        task_id = 'xyz'
        subtask_id = 'xxyyzz'

        tc.resource_failure(task_id, 'reason')
        assert not task_server.send_task_failed.called

        tc.assigned_subtask = ComputeTaskDef(
            task_id=task_id,
            subtask_id=subtask_id,
        )

        tc.resource_failure(task_id, 'reason')
        assert task_server.send_task_failed.called

    def test_computation(self):  # pylint: disable=too-many-statements
        # FIXME Refactor too single tests and remove disable too many
        ctd = ComputeTaskDef()
        ctd['task_id'] = "xyz"
        ctd['subtask_id'] = "xxyyzz"
        ctd['extra_data'] = {}
        ctd['extra_data']['src_code'] = \
            "cnt=0\n" \
            "for i in range(10000):\n" \
            "\tcnt += 1\n" \
            "output={'data': cnt, 'result_type': 0}"
        ctd['deadline'] = timeout_to_deadline(10)
        ctd['resources'] = ["abcd", "efgh"]

        task_server = self.task_server
        task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(
                subtask_timeout=5,
                deadline=timeout_to_deadline(5)
            ),
            ctd['task_id']: mock.Mock(
                subtask_timeout=5,
                deadline=timeout_to_deadline(20)
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(task_server, use_docker_manager=False,
                          finished_cb=mock_finished)

        self.assertEqual(tc.assigned_subtask, None)
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtask, ctd)
        self.assertLessEqual(tc.assigned_subtask['deadline'],
                             timeout_to_deadline(10))
        tc.task_server.request_resource.assert_called_with(
            "xyz", "xxyyzz", ["abcd", "efgh"])

        assert tc.resource_collected("xyz")
        assert tc.counting_thread is None
        assert tc.assigned_subtask is None
        task_server.send_task_failed.assert_called_with(
            "xxyyzz", "xyz", "Host direct task not supported")

        tc.support_direct_computation = True
        tc.task_given(ctd)
        assert tc.resource_collected("xyz")
        assert tc.counting_thread is not None
        self.assertGreater(tc.counting_thread.time_to_compute, 8)
        self.assertLessEqual(tc.counting_thread.time_to_compute, 10)
        mock_finished.assert_called_once_with()
        mock_finished.reset_mock()
        self.__wait_for_tasks(tc)

        prev_task_failed_count = task_server.send_task_failed.call_count
        self.assertIsNone(tc.counting_thread)
        self.assertIsNone(tc.assigned_subtask)
        assert task_server.send_task_failed.call_count == prev_task_failed_count
        self.assertTrue(task_server.send_results.called)
        args = task_server.send_results.call_args[0]
        self.assertEqual(args[0], "xxyyzz")
        self.assertEqual(args[1], "xyz")
        self.assertEqual(args[2]["data"], 10000)
        mock_finished.assert_called_once_with()
        mock_finished.reset_mock()

        ctd['subtask_id'] = "aabbcc"
        ctd['extra_data']['src_code'] = "raise Exception('some exception')"
        ctd['deadline'] = timeout_to_deadline(5)
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtask, ctd)
        self.assertLessEqual(tc.assigned_subtask['deadline'],
                             timeout_to_deadline(5))
        tc.task_server.request_resource.assert_called_with(
            "xyz", "aabbcc", ["abcd", "efgh"])
        self.assertTrue(tc.resource_collected("xyz"))
        self.__wait_for_tasks(tc)

        self.assertIsNone(tc.counting_thread)
        self.assertIsNone(tc.assigned_subtask)
        task_server.send_task_failed.assert_called_with(
            "aabbcc", "xyz", 'some exception')
        mock_finished.assert_called_once_with()
        mock_finished.reset_mock()

        ctd['subtask_id'] = "aabbcc2"
        ctd['extra_data']['src_code'] = "print('Hello world')"
        ctd['deadline'] = timeout_to_deadline(5)
        tc.task_given(ctd)
        self.assertTrue(tc.resource_collected("xyz"))
        self.__wait_for_tasks(tc)

        task_server.send_task_failed.assert_called_with(
            "aabbcc2", "xyz", "Wrong result format")
        mock_finished.assert_called_once_with()
        mock_finished.reset_mock()

        task_server.task_keeper.task_headers["xyz"].deadline = \
            timeout_to_deadline(20)
        ctd['subtask_id'] = "aabbcc3"
        ctd['extra_data']['src_code'] = "output={'data': 0, 'result_type': 0}"
        ctd['deadline'] = timeout_to_deadline(40)
        tc.task_given(ctd)
        self.assertTrue(tc.resource_collected("xyz"))
        self.assertIsNotNone(tc.counting_thread)
        self.assertGreater(tc.counting_thread.time_to_compute, 10)
        self.assertLessEqual(tc.counting_thread.time_to_compute, 20)
        self.__wait_for_tasks(tc)

        ctd['subtask_id'] = "xxyyzz2"
        ctd['deadline'] = timeout_to_deadline(1)
        tc.task_given(ctd)
        self.assertTrue(tc.resource_collected("xyz"))
        mock_finished.assert_called_once_with()
        mock_finished.reset_mock()
        tt = tc.counting_thread
        tc.task_computed(tc.counting_thread)
        self.assertIsNone(tc.counting_thread)
        mock_finished.assert_called_once_with()
        mock_finished.reset_mock()
        task_server.send_task_failed.assert_called_with(
            "xxyyzz2", "xyz", "Wrong result format")
        tt.end_comp()
        time.sleep(0.5)
        if tt.is_alive():
            tt.join(timeout=5)

    def test_host_state(self):
        task_server = self.task_server
        tc = TaskComputer(task_server, use_docker_manager=False)
        self.assertEqual(tc.get_host_state(), "Idle")
        tc.counting_thread = mock.Mock()
        self.assertEqual(tc.get_host_state(), "Computing")

    def test_change_config(self):
        task_server = self.task_server

        tc = TaskComputer(task_server, use_docker_manager=False)
        tc.docker_manager = mock.Mock(spec=DockerManager, hypervisor=None)

        tc.use_docker_manager = False
        tc.change_config(mock.Mock(), in_background=False)
        assert not tc.docker_manager.update_config.called

        tc.use_docker_manager = True

        def _update_config(status_callback, *_, **__):
            status_callback()
        tc.docker_manager.update_config = _update_config

        tc.change_config(mock.Mock(), in_background=False)

        # pylint: disable=unused-argument
        def _update_config_2(status_callback, done_callback, *_, **__):
            done_callback(False)
        tc.docker_manager.update_config = _update_config_2

        tc.change_config(mock.Mock(), in_background=False)

    def test_event_listeners(self):
        client = mock.Mock()
        task_server = self.task_server

        tc = TaskComputer(task_server, use_docker_manager=False)

        tc.lock_config(True)
        tc.lock_config(False)

        listener = ClientTaskComputerEventListener(client)
        tc.register_listener(listener)

        tc.lock_config(True)
        client.lock_config.assert_called_with(True)

        tc.lock_config(False)
        client.lock_config.assert_called_with(False)

    @mock.patch('golem.task.taskthread.TaskThread.start')
    def test_compute_task(self, start):

        task_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())
        task_computer = mock.Mock()
        compute_task = TaskComputer._TaskComputer__compute_task

        dir_manager = task_computer.dir_manager
        dir_manager.get_task_resource_dir.return_value = self.tempdir + '_res'
        dir_manager.get_task_temporary_dir.return_value = self.tempdir + '_tmp'

        task_computer.lock = Lock()
        task_computer.dir_lock = Lock()

        task_computer.assigned_subtask = ComputeTaskDef(
            task_id=task_id,
            subtask_id=subtask_id,
        )
        task_computer.task_server.task_keeper.task_headers = {
            task_id: None
        }

        args = (task_computer, subtask_id)
        kwargs = dict(
            docker_images=[],
            extra_data=mock.Mock(),
            subtask_deadline=time.time() + 3600
        )

        compute_task(*args, **kwargs)
        assert not start.called

        header = mock.Mock(deadline=time.time() + 3600)
        task_computer.task_server.task_keeper.task_headers[task_id] = header

        compute_task(*args, **kwargs)
        assert start.called

    @staticmethod
    def __wait_for_tasks(tc):
        if tc.counting_thread is not None:
            tc.counting_thread.join()
        else:
            print('counting thread is None')

    def test_get_environment_no_assigned_subtask(self):
        tc = TaskComputer(self.task_server, use_docker_manager=False)
        assert tc.get_environment() is None

    def test_get_environment(self):
        task_server = self.task_server
        task_server.task_keeper.task_headers = {
            "task_id": mock.Mock(
                environment="env"
            )
        }

        tc = TaskComputer(task_server, use_docker_manager=False)
        tc.assigned_subtask = ComputeTaskDef()
        tc.assigned_subtask['task_id'] = "task_id"
        assert tc.get_environment() == "env"


@ci_skip
class TestTaskThread(DatabaseFixture):
    def test_thread(self):
        ts = mock.MagicMock()
        ts.config_desc = ClientConfigDescriptor()
        ts.benchmark_manager.benchmarks_needed.return_value = False
        ts.get_task_computer_root.return_value = self.new_path

        tc = TaskComputer(ts, use_docker_manager=False)

        tt = self._new_task_thread(tc)
        sync_wait(tt.start())

        self.assertGreater(tt.end_time - tt.start_time, 0)
        self.assertLess(tt.end_time - tt.start_time, 20)

    def test_fail(self):
        first_error = Exception("First error message")
        second_error = Exception("Second error message")

        tt = self._new_task_thread(mock.Mock())
        tt._fail(first_error)

        assert tt.error is True
        assert tt.done is True
        assert tt.error_msg == str(first_error)

        tt._fail(second_error)
        assert tt.error is True
        assert tt.done is True
        assert tt.error_msg == str(first_error)

    def _new_task_thread(self, task_computer):
        files = self.additional_dir_content([0, [1], [1], [1], [1]])
        src_code = """
                   cnt = 0
                   for i in range(1000000):
                       cnt += 1
                   output = cnt
                   """

        return PyTaskThread(extra_data={'src_code': src_code},
                            res_path=os.path.dirname(files[0]),
                            tmp_path=os.path.dirname(files[1]),
                            timeout=20)


class TestTaskMonitor(DatabaseFixture):
    def test_task_computed(self):
        """golem.monitor signal"""
        from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
        from golem.monitor.monitor import SystemMonitor
        from golem.monitorconfig import MONITOR_CONFIG
        #  hold reference to avoid GC of monitor
        client_mock = mock.MagicMock()
        client_mock.cliid = 'CLIID'
        client_mock.sessid = 'SESSID'
        client_mock.config_desc = ClientConfigDescriptor()
        os_info = OSInfo(
            'linux',
            'Linux',
            '1',
            '1.2.3'
        )
        monitor = SystemMonitor(  # noqa pylint: disable=unused-variable
            NodeMetadataModel(client_mock, os_info, "3.1337"),
            MONITOR_CONFIG)
        task_server = mock.MagicMock()
        task_server.config_desc = ClientConfigDescriptor()
        task_server.benchmark_manager.benchmarks_needed.return_value = False
        task_server.get_task_computer_root.return_value = self.new_path

        task = TaskComputer(task_server, use_docker_manager=False)

        task_thread = mock.MagicMock()
        task_thread.start_time = time.time()
        duration = random.randint(1, 100)
        task_thread.end_time = task_thread.start_time + duration

        def prepare():
            subtask = mock.MagicMock()
            subtask_id = random.randint(3000, 4000)
            subtask['subtask_id'] = subtask_id
            task_server\
                .task_keeper.task_headers[subtask_id].subtask_timeout = duration

            task.assigned_subtask = subtask

        def check(expected):
            with mock.patch('golem.monitor.monitor.SenderThread.send') \
                    as mock_send:
                task.task_computed(task_thread)
                self.assertEqual(mock_send.call_count, 1)
                result = mock_send.call_args[0][0].dict_repr()
                for key in ('cliid', 'sessid', 'timestamp'):
                    del result[key]
                expected_d = {
                    'type': 'ComputationTime',
                    'success': expected,
                    'value': duration,
                }
                self.assertEqual(expected_d, result)

        # error case
        prepare()
        task_thread.error = True
        check(False)

        # success case
        prepare()
        task_thread.error = False
        task_thread.error_msg = None
        task_thread.result = {'data': 'oh senora!!!'}
        check(True)

        # default case (error)
        prepare()
        task_thread.result = None
        check(False)
