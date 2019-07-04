import os
import random
from pathlib import Path
from threading import Lock
import time
import unittest.mock as mock
import uuid

from golem_messages.message import ComputeTaskDef
from twisted.internet.defer import Deferred

from golem.client import ClientTaskComputerEventListener
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline
from golem.core.deferred import sync_wait
from golem.docker.manager import DockerManager
from golem.envs.docker.cpu import DockerCPUConfig, DockerCPUEnvironment
from golem.task.taskcomputer import TaskComputer, PyTaskThread
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip
from golem.tools.assertlogs import LogTestCase
from golem.tools.os_info import OSInfo


class TestTaskComputerBase(DatabaseFixture, LogTestCase):

    @mock.patch('golem.task.taskcomputer.TaskComputer.change_docker_config')
    @mock.patch('golem.task.taskcomputer.DockerManager')
    def setUp(self, docker_manager, _):
        super().setUp()  # pylint: disable=arguments-differ

        task_server = mock.MagicMock()
        task_server.benchmark_manager.benchmarks_needed.return_value = False
        task_server.get_task_computer_root.return_value = self.path
        task_server.config_desc = ClientConfigDescriptor()
        self.task_server = task_server

        self.docker_cpu_env = mock.Mock(spec=DockerCPUEnvironment)
        self.docker_manager = mock.Mock(spec=DockerManager, hypervisor=None)
        docker_manager.install.return_value = self.docker_manager

        self.task_computer = TaskComputer(
            self.task_server,
            self.docker_cpu_env)

        self.docker_manager.reset_mock()
        self.docker_cpu_env.reset_mock()


@ci_skip
class TestTaskComputer(TestTaskComputerBase):

    def test_init(self):
        tc = TaskComputer(
            self.task_server,
            self.docker_cpu_env,
            use_docker_manager=False)
        self.assertIsInstance(tc, TaskComputer)

    def test_check_timeout(self):
        self.task_computer.counting_thread = mock.Mock()
        self.task_computer.check_timeout()
        self.task_computer.counting_thread.check_timeout.assert_called_once()

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
        tc = TaskComputer(
            task_server,
            self.docker_cpu_env,
            use_docker_manager=False,
            finished_cb=mock_finished)

        self.assertEqual(tc.assigned_subtask, None)
        tc.task_given(ctd)
        self.assertEqual(tc.assigned_subtask, ctd)
        self.assertLessEqual(tc.assigned_subtask['deadline'],
                             timeout_to_deadline(10))

        tc.start_computation()
        assert tc.counting_thread is None
        assert tc.assigned_subtask is None
        task_server.send_task_failed.assert_called_with(
            "xxyyzz", "xyz", "Host direct task not supported")

        tc.support_direct_computation = True
        tc.task_given(ctd)
        tc.start_computation()
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
        tc.start_computation()
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
        tc.start_computation()
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
        tc.start_computation()
        self.assertIsNotNone(tc.counting_thread)
        self.assertGreater(tc.counting_thread.time_to_compute, 10)
        self.assertLessEqual(tc.counting_thread.time_to_compute, 20)
        self.__wait_for_tasks(tc)

        ctd['subtask_id'] = "xxyyzz2"
        ctd['deadline'] = timeout_to_deadline(1)
        tc.task_given(ctd)
        tc.start_computation()
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
        tc = TaskComputer(
            task_server,
            self.docker_cpu_env,
            use_docker_manager=False)
        self.assertEqual(tc.get_host_state(), "Idle")
        tc.counting_thread = mock.Mock()
        self.assertEqual(tc.get_host_state(), "Computing")

    def test_event_listeners(self):
        client = mock.Mock()
        task_server = self.task_server

        tc = TaskComputer(
            task_server,
            self.docker_cpu_env,
            use_docker_manager=False)

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
        compute_task = TaskComputer.start_computation

        dir_manager = task_computer.dir_manager
        dir_manager.get_task_resource_dir.return_value = self.tempdir + '_res'
        dir_manager.get_task_temporary_dir.return_value = self.tempdir + '_tmp'

        task_computer.lock = Lock()
        task_computer.dir_lock = Lock()

        task_computer.assigned_subtask = ComputeTaskDef(
            task_id=task_id,
            subtask_id=subtask_id,
            docker_images=[],
            extra_data=mock.Mock(),
            deadline=time.time() + 3600
        )
        task_computer.task_server.task_keeper.task_headers = {
            task_id: None
        }

        compute_task(task_computer)
        assert not start.called

        header = mock.Mock(deadline=time.time() + 3600)
        task_computer.task_server.task_keeper.task_headers[task_id] = header

        compute_task(task_computer)
        assert start.called

    @staticmethod
    def __wait_for_tasks(tc):
        if tc.counting_thread is not None:
            tc.counting_thread.join()
        else:
            print('counting thread is None')

    def test_get_environment_no_assigned_subtask(self):
        tc = TaskComputer(
            self.task_server,
            self.docker_cpu_env,
            use_docker_manager=False)
        assert tc.get_environment() is None

    def test_get_environment(self):
        task_server = self.task_server
        task_server.task_keeper.task_headers = {
            "task_id": mock.Mock(
                environment="env"
            )
        }

        tc = TaskComputer(
            task_server,
            self.docker_cpu_env,
            use_docker_manager=False)
        tc.assigned_subtask = ComputeTaskDef()
        tc.assigned_subtask['task_id'] = "task_id"
        assert tc.get_environment() == "env"


@ci_skip
class TestTaskThread(DatabaseFixture):

    @mock.patch(
        'golem.envs.docker.cpu.deferToThread',
        lambda f, *args, **kwargs: f(*args, **kwargs))
    def test_thread(self):
        ts = mock.MagicMock()
        ts.config_desc = ClientConfigDescriptor()
        ts.config_desc.max_memory_size = 1024 * 1024  # 1 GiB
        ts.config_desc.num_cores = 1
        ts.benchmark_manager.benchmarks_needed.return_value = False
        ts.get_task_computer_root.return_value = self.new_path

        tc = TaskComputer(
            ts,
            mock.Mock(spec=DockerCPUEnvironment),
            use_docker_manager=False)

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
        task_server.config_desc.max_memory_size = 1024 * 1024  # 1 GiB
        task_server.config_desc.num_cores = 1
        task_server.benchmark_manager.benchmarks_needed.return_value = False
        task_server.get_task_computer_root.return_value = self.new_path

        task = TaskComputer(
            task_server,
            mock.Mock(spec=DockerCPUEnvironment),
            use_docker_manager=False)

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


@mock.patch('golem.task.taskcomputer.TaskComputer.change_docker_config')
class TestChangeConfig(TestTaskComputerBase):

    @mock.patch('golem.task.taskcomputer.TaskComputer.change_docker_config')
    @mock.patch('golem.task.taskcomputer.DockerManager')
    def setUp(self, *_):
        super().setUp()
        self.task_computer = TaskComputer(
            self.task_server,
            self.docker_cpu_env)

    def test_root_path(self, change_docker_config):
        self.task_server.get_task_computer_root.return_value = '/test'
        config_desc = ClientConfigDescriptor()
        self.task_computer.change_config(config_desc)
        self.assertEqual(self.task_computer.dir_manager.root_path, '/test')
        change_docker_config.assert_called_once_with(
            config_desc=config_desc,
            work_dirs=[Path('/test')],
            run_benchmarks=False,
            in_background=True
        )

    def _test_compute_tasks(self, accept_tasks, in_shutdown, expected):
        config_desc = ClientConfigDescriptor()
        config_desc.accept_tasks = accept_tasks
        config_desc.in_shutdown = in_shutdown
        self.task_computer.change_config(config_desc)
        self.assertEqual(self.task_computer.compute_tasks, expected)

    def test_compute_tasks(self, _):
        self._test_compute_tasks(
            accept_tasks=True,
            in_shutdown=True,
            expected=False
        )
        self._test_compute_tasks(
            accept_tasks=True,
            in_shutdown=False,
            expected=True
        )
        self._test_compute_tasks(
            accept_tasks=False,
            in_shutdown=True,
            expected=False
        )
        self._test_compute_tasks(
            accept_tasks=False,
            in_shutdown=False,
            expected=False
        )

    def test_not_in_background(self, change_docker_config):
        config_desc = ClientConfigDescriptor()
        self.task_computer.change_config(config_desc, in_background=False)
        change_docker_config.assert_called_once_with(
            config_desc=config_desc,
            work_dirs=mock.ANY,
            run_benchmarks=False,
            in_background=False
        )

    def test_run_benchmarks(self, change_docker_config):
        config_desc = ClientConfigDescriptor()
        self.task_computer.change_config(config_desc, run_benchmarks=True)
        change_docker_config.assert_called_once_with(
            config_desc=config_desc,
            work_dirs=mock.ANY,
            run_benchmarks=True,
            in_background=True
        )


@mock.patch('golem.task.taskcomputer.ProviderTimer')
class TestTaskGiven(TestTaskComputerBase):

    def test_ok(self, provider_timer):
        ctd = mock.Mock()
        self.task_computer.task_given(ctd)
        self.assertEqual(self.task_computer.assigned_subtask, ctd)
        provider_timer.start.assert_called_once_with()

    def test_already_assigned(self, provider_timer):
        self.task_computer.assigned_subtask = mock.Mock()
        ctd = mock.Mock()
        with self.assertRaises(AssertionError):
            self.task_computer.task_given(ctd)
        provider_timer.start.assert_not_called()


class TestChangeDockerConfig(TestTaskComputerBase):

    def test_docket_cpu_env_update(self):
        # Given
        config_desc = ClientConfigDescriptor()
        config_desc.num_cores = 3
        config_desc.max_memory_size = 3000 * 1024
        work_dirs = [Path('/test')]

        # When
        self.task_computer.change_docker_config(
            config_desc=config_desc,
            work_dirs=work_dirs,
            run_benchmarks=False
        )

        # Then
        self.docker_cpu_env.clean_up.assert_called_once_with()
        self.docker_cpu_env.update_config.assert_called_once_with(
            DockerCPUConfig(
                work_dirs=work_dirs,
                cpu_count=3,
                memory_mb=3000
            ))
        self.docker_cpu_env.prepare.assert_called_once_with()

    def test_no_hypervisor_no_benchmark(self):
        # Given
        config_desc = ClientConfigDescriptor()
        work_dirs = [Path('/test')]

        # When
        result = self.task_computer.change_docker_config(
            config_desc=config_desc,
            work_dirs=work_dirs,
            run_benchmarks=False
        )

        # Then
        self.assertIsInstance(result, Deferred)
        self.docker_manager.build_config.assert_called_once_with(config_desc)
        self.docker_manager.update_config.assert_not_called()
        self.task_server.benchmark_manager.run_all_benchmarks \
            .assert_not_called()

    def test_no_hypervisor_run_benchmark(self):
        # Given
        config_desc = ClientConfigDescriptor()
        work_dirs = [Path('/test')]

        # When
        result = self.task_computer.change_docker_config(
            config_desc=config_desc,
            work_dirs=work_dirs,
            run_benchmarks=True
        )

        # Then
        self.assertIsInstance(result, Deferred)
        self.docker_manager.build_config.assert_called_once_with(config_desc)
        self.docker_manager.update_config.assert_not_called()
        self.task_server.benchmark_manager.run_all_benchmarks\
            .assert_called_once()

    @mock.patch('golem.task.taskcomputer.TaskComputer.lock_config')
    def test_with_hypervisor(self, lock_config):
        # Given
        self.docker_manager.hypervisor = mock.Mock()
        config_desc = ClientConfigDescriptor()
        work_dirs = [Path('/test')]

        # When
        result = self.task_computer.change_docker_config(
            config_desc=config_desc,
            work_dirs=work_dirs,
            run_benchmarks=False
        )

        # Then
        self.assertIsInstance(result, Deferred)
        self.docker_manager.build_config.assert_called_once_with(config_desc)
        lock_config.assert_called_once_with(True)
        self.assertFalse(self.task_computer.runnable)

        self.docker_manager.update_config.assert_called_once()
        _, kwargs = self.docker_manager.update_config.call_args
        self.assertEqual(kwargs.get('work_dirs'), work_dirs)
        self.assertEqual(kwargs.get('in_background'), True)

        # Check status callback
        status_callback = kwargs.get('status_callback')
        with mock.patch.object(self.task_computer, 'is_computing') as is_comp:
            is_comp.return_value = True
            self.assertTrue(status_callback())
            is_comp.assert_called_once()

        # Check done callback -- variant 1: config does not differ
        done_callback = kwargs.get('done_callback')
        lock_config.reset_mock()
        with mock.patch.object(result, 'callback') as result_callback:
            done_callback(False)
            self.task_server.benchmark_manager.run_all_benchmarks\
                .assert_not_called()
            result_callback.assert_called_once_with('Benchmarks not executed')
            lock_config.assert_called_once_with(False)
            self.assertTrue(self.task_computer.runnable)

        # Check done callback -- variant 1: config does differ
        done_callback = kwargs.get('done_callback')
        lock_config.reset_mock()
        self.task_computer.runnable = False
        done_callback(True)
        self.task_server.benchmark_manager.run_all_benchmarks \
            .assert_called_once()
        lock_config.assert_called_once_with(False)
        self.assertTrue(self.task_computer.runnable)


class TestTaskInterrupted(TestTaskComputerBase):

    def test_no_task_assigned(self):
        with self.assertRaises(AssertionError):
            self.task_computer.task_interrupted()

    @mock.patch('golem.task.taskcomputer.TaskComputer._task_finished')
    def test_ok(self, task_finished):
        self.task_computer.assigned_subtask = mock.Mock()
        self.task_computer.task_interrupted()
        task_finished.assert_called_once_with()


class TestTaskFinished(TestTaskComputerBase):

    def test_no_assigned_subtask(self):
        with self.assertRaises(AssertionError):
            self.task_computer._task_finished()

    @mock.patch('golem.task.taskcomputer.dispatcher')
    @mock.patch('golem.task.taskcomputer.ProviderTimer')
    def test_ok(self, provider_timer, dispatcher):
        ctd = ComputeTaskDef(
            task_id='test_task',
            subtask_id='test_subtask',
            performance=123
        )
        self.task_computer.assigned_subtask = ctd
        self.task_computer.counting_thread = mock.Mock()
        self.task_computer.finished_cb = mock.Mock()

        self.task_computer._task_finished()
        self.assertIsNone(self.task_computer.assigned_subtask)
        self.assertIsNone(self.task_computer.counting_thread)
        provider_timer.finish.assert_called_once_with()
        dispatcher.send.assert_called_once_with(
            signal='golem.taskcomputer',
            event='subtask_finished',
            subtask_id=ctd['subtask_id'],
            min_performance=ctd['performance']
        )
        self.task_server.task_keeper.task_ended.assert_called_once_with(
            ctd['task_id'])
        self.task_computer.finished_cb.assert_called_once_with()
