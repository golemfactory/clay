import os
import random
from threading import Lock
import time
import unittest.mock as mock
import uuid

from ethereum.utils import denoms
from pydispatch import dispatcher

from golem_messages import factories as msg_factories
from golem_messages.message import ComputeTaskDef, TaskFailure
from twisted.internet import defer
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline
from golem.core.deferred import sync_wait
from golem.docker.manager import DockerManager
from golem.envs.docker.cpu import DockerCPUEnvironment
from golem.task.taskcomputer import TaskComputer, PyTaskThread, TaskComputation
from golem.task.taskserver import TaskServer
from golem.task.taskthread import JobException
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip
from golem.tools.assertlogs import LogTestCase
from golem.tools.os_info import OSInfo


@ci_skip
class TestTaskComputer(DatabaseFixture, LogTestCase):

    @mock.patch('golem.task.taskcomputer.DockerManager')
    def setUp(self, docker_manager):
        super().setUp()  # pylint: disable=arguments-differ

        task_server = mock.MagicMock()
        task_server.benchmark_manager.benchmarks_needed.return_value = False
        task_server.get_task_computer_root.return_value = self.path
        task_server.config_desc = ClientConfigDescriptor()
        self.task_server = task_server

        self.docker_manager = mock.Mock(spec=DockerManager, hypervisor=None)
        docker_manager.install.return_value = self.docker_manager
        self.task_computer = TaskComputer(self.task_server)
        self.docker_manager.reset_mock()

    def test_init(self):
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False)
        self.assertIsInstance(tc, TaskComputer)

    def test_check_timeout(self):
        cc = TaskComputation(
            task_computer=self.task_computer,
            assigned_subtask=mock.Mock())
        cc.counting_thread = mock.Mock()
        self.task_computer.assigned_subtasks.append(cc)
        self.task_computer.check_timeout()
        cc.counting_thread.check_timeout.assert_called_once()

    def test_computation_not_supported(self):
        # Given
        subtask_timeout = 5

        ctd = msg_factories.tasks.ComputeTaskDefFactory()

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)

        # When
        tc.task_given(ctd)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])

        # Then
        self.assertFalse(tc.assigned_subtasks)
        self.task_server.send_task_failed.assert_called_with(
            ctd['subtask_id'],
            ctd['task_id'],
            "Host direct task not supported"
        )

    def test_computation_ok(self):
        # Given
        subtask_timeout = 5

        ctd = msg_factories.tasks.ComputeTaskDefFactory()
        ctd['extra_data']['src_code'] = \
            "cnt=0\n" \
            "for i in range(10000):\n" \
            "\tcnt += 1\n" \
            "output={'data': cnt, 'result_type': 0}"

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)
        tc.support_direct_computation = True

        # When
        tc.task_given(ctd)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])
        self.__wait_for_tasks(tc)

        # Then
        self.assertFalse(tc.assigned_subtasks)
        self.assertTrue(self.task_server.send_results.called)
        kwargs = self.task_server.send_results.call_args[1]
        self.assertEqual(kwargs['subtask_id'], ctd['subtask_id'])
        self.assertEqual(kwargs['task_id'], ctd['task_id'])
        self.assertEqual(kwargs['result'], 10000)
        mock_finished.assert_called_once_with()

    def test_computation_failure(self):
        # Given
        subtask_timeout = 5

        ctd = msg_factories.tasks.ComputeTaskDefFactory()
        ctd['extra_data']['src_code'] = "raise Exception('some exception')"

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)
        tc.support_direct_computation = True

        # When
        tc.task_given(ctd)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])

        # Then
        self.assertEqual(len(tc.assigned_subtasks), 1)
        assigned_subtask = tc.assigned_subtasks[0].assigned_subtask
        self.__wait_for_tasks(tc)
        self.assertLessEqual(assigned_subtask['deadline'],
                             ctd['deadline'])
        self.task_server.send_task_failed.assert_called_with(
            ctd['subtask_id'],
            ctd['task_id'],
            'some exception',
            TaskFailure.DEFAULT_REASON)
        mock_finished.assert_called_once_with()

    def test_computation_wrong_format(self):
        # Given
        subtask_timeout = 5

        ctd = msg_factories.tasks.ComputeTaskDefFactory()
        ctd['extra_data']['src_code'] = "print('Hello world')"

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)
        tc.support_direct_computation = True

        # When
        tc.task_given(ctd)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])
        self.__wait_for_tasks(tc)

        # Then
        self.task_server.send_task_failed.assert_called_with(
            ctd['subtask_id'], ctd['task_id'], "Wrong result format")
        mock_finished.assert_called_once_with()

    def test_computation_time_elapsed(self):
        # Given
        subtask_timeout = 5
        deadline = timeout_to_deadline(20)

        ctd = msg_factories.tasks.ComputeTaskDefFactory(deadline=deadline)
        ctd['extra_data']['src_code'] = "output={'data': 0, 'result_type': 0}"

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)
        tc.support_direct_computation = True

        # When
        tc.task_given(ctd)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])

        # Then
        self.assertTrue(tc._is_computing())
        self.assertGreater(
            tc.assigned_subtasks[0].counting_thread.time_to_compute, 10)
        self.assertLessEqual(
            tc.assigned_subtasks[0].counting_thread.time_to_compute, 20)
        self.__wait_for_tasks(tc)

    def test_computation_task_thread(self):
        # Given
        subtask_timeout = 1
        deadline = timeout_to_deadline(1)

        ctd = msg_factories.tasks.ComputeTaskDefFactory(deadline=deadline)
        ctd['extra_data']['src_code'] = "output={'data': 0, 'result_type': 0}"

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)
        tc.support_direct_computation = True

        # When
        tc.task_given(ctd)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])
        assigned_subtask = tc.assigned_subtasks[0]
        task_thread = assigned_subtask.counting_thread
        assigned_subtask.task_computed(task_thread)

        # Then
        self.assertFalse(tc._is_computing())
        mock_finished.assert_called_once_with()
        task_thread.end_comp()
        time.sleep(0.5)
        if task_thread.is_alive():
            task_thread.join(timeout=5)

    def test_computation_cpu_limit(self):
        # Given
        subtask_budget = 1 * denoms.ether   # 1 GNT
        subtask_timeout = 5
        cpu_time_limit = 1800   # CPU time limit in seconds

        ctd = msg_factories.tasks.ComputeTaskDefFactory()
        ctd['extra_data']['src_code'] = "output={'data': 0, 'result_type': 0}"

        self.task_server.task_keeper.task_headers = {
            ctd['subtask_id']: mock.Mock(subtask_timeout=subtask_timeout),
            ctd['task_id']: mock.Mock(
                subtask_timeout=subtask_timeout,
                deadline=ctd['deadline'],
                subtask_budget=subtask_budget
            )
        }

        mock_finished = mock.Mock()
        tc = TaskComputer(
            self.task_server,
            use_docker_manager=False,
            finished_cb=mock_finished)
        tc.support_direct_computation = True

        # When
        tc.task_given(ctd, cpu_time_limit)
        tc.start_computation(ctd['task_id'], ctd['subtask_id'])

        # Then
        assigned_subtask = tc.assigned_subtasks[0]
        self.assertEqual(cpu_time_limit, assigned_subtask.cpu_limit)
        self.__wait_for_tasks(tc)

    @mock.patch('golem.task.taskthread.TaskThread.start')
    def test_compute_task(self, start):

        task_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())
        task_computer = mock.Mock()

        compute_task = TaskComputation.start_computation

        dir_manager = task_computer.dir_manager
        dir_manager.get_task_resource_dir.return_value = self.tempdir + '_res'
        dir_manager.get_task_temporary_dir.return_value = self.tempdir + '_tmp'

        task_computer.lock = Lock()
        task_computer.dir_lock = Lock()

        task_part = TaskComputation(
            task_computer=task_computer, assigned_subtask=ComputeTaskDef(
                task_id=task_id,
                subtask_id=subtask_id,
                docker_images=[],
                extra_data=mock.Mock(),
                deadline=time.time() + 3600))
        task_computer.task_server.task_keeper.task_headers = {
            task_id: None
        }

        compute_task(task_part)
        assert not start.called

        header = mock.Mock(deadline=time.time() + 3600)
        task_computer.task_server.task_keeper.task_headers[task_id] = header

        compute_task(task_part)
        assert start.called

    @staticmethod
    def __wait_for_tasks(tc):
        for c in tc.assigned_subtasks:
            if c.counting_thread is not None:
                c.counting_thread.join()
        else:
            print('counting thread is None')

    def test_get_environment_no_assigned_subtask(self):
        tc = TaskComputer(
            self.task_server,
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
            use_docker_manager=False)
        ctd = ComputeTaskDef()
        ctd['task_id'] = "task_id"
        tc.task_given(ctd)
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

        self.assertIsNotNone(tt.error)
        assert tt.done is True
        assert tt.error_msg == str(first_error)

        tt._fail(second_error)
        self.assertIsNotNone(tt.error)
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

            task.task_given(subtask)

        def check(expected):
            listener = mock.Mock()
            kwargs = {
                'signal': 'golem.monitor',
            }
            dispatcher.connect(
                listener,
                **kwargs,
            )
            task.assigned_subtasks[-1].task_computed(task_thread)
            listener.assert_called_once_with(
                event='computation_time_spent',
                sender=mock.ANY,
                value=duration,
                success=expected,
                **kwargs,
            )

        # error case
        prepare()
        task_thread.error = JobException()
        check(False)

        # success case
        prepare()
        task_thread.error = None
        task_thread.error_msg = None
        task_thread.result = {'data': 'oh senora!!!'}
        check(True)

        # default case (error)
        prepare()
        task_thread.result = None
        check(False)


class TestTaskComputerBase(TwistedTestCase):

    @mock.patch('golem.task.taskcomputer.IntStatsKeeper')
    @mock.patch('golem.task.taskcomputer.DockerManager')
    def setUp(self, docker_manager, _):
        super().setUp()
        self.task_server = mock.Mock(
            spec=TaskServer,
            config_desc=ClientConfigDescriptor(),
            task_keeper=mock.Mock())
        self.docker_cpu_env = mock.Mock(spec=DockerCPUEnvironment)
        self.docker_manager = mock.Mock(spec=DockerManager, hypervisor=None)
        docker_manager.install.return_value = self.docker_manager
        self.task_computer = TaskComputer(
            self.task_server,
            self.docker_cpu_env)


class TestChangeConfig(TestTaskComputerBase):

    def setUp(self):
        super().setUp()
        self.docker_cpu_env.clean_up.return_value = defer.succeed(None)
        self.docker_cpu_env.prepare.return_value = defer.succeed(None)

    @defer.inlineCallbacks
    def test_root_path(self):
        self.task_server.get_task_computer_root.return_value = '/test'
        config_desc = ClientConfigDescriptor()

        yield self.task_computer.change_config(config_desc)
        self.assertEqual(self.task_computer.dir_manager.root_path, '/test')

    @defer.inlineCallbacks
    def test_update_docker_manager_config(self):
        def _update_config(done_callback, *_, **__):
            done_callback(True)

        self.docker_manager.hypervisor = mock.Mock()
        self.docker_manager.update_config.side_effect = _update_config
        self.task_server.get_task_computer_root.return_value = '/test'
        config_desc = ClientConfigDescriptor()

        result = yield self.task_computer.change_config(config_desc)
        self.assertTrue(result)
        self.docker_manager.build_config.assert_called_once_with(config_desc)
        self.docker_manager.update_config.assert_called_once()


@mock.patch('golem.task.taskcomputer.ProviderTimer')
class TestTaskGiven(TestTaskComputerBase):

    def test_ok(self, provider_timer):
        ctd = mock.Mock()
        self.task_computer.task_given(ctd)
        self.assertEqual(
            self.task_computer.assigned_subtasks[-1].assigned_subtask,
            ctd)
        provider_timer.start.assert_called_once_with()


class TestTaskInterrupted(TestTaskComputerBase):

    def test_no_task_assigned(self):
        with self.assertRaises(AssertionError):
            task_id = '86d866fe-0824-4aab-a407-e02067fad962'
            self.task_computer.task_interrupted(task_id)

    @mock.patch('golem.task.taskcomputer.TaskComputer.task_finished')
    def test_ok(self, task_finished):
        task_id = '86d866fe-0824-4aab-a407-e02067fad962'
        ctd = {
            'task_id': task_id,
            'subtask_id': 'b8e23388-0792-11ea-97ca-67a3db66bbfb'
        }
        self.task_computer.task_given(ctd)
        self.task_computer.task_interrupted(task_id)
        task_finished.assert_called_once()


class TestTaskFinished(TestTaskComputerBase):

    def test_no_assigned_subtask(self):
        with self.assertRaises(AssertionError):
            self.task_computer.task_finished(
                TaskComputation(
                    task_computer=self.task_computer,
                    assigned_subtask=mock.Mock()))

    @mock.patch('golem.task.taskcomputer.dispatcher')
    @mock.patch('golem.task.taskcomputer.ProviderTimer')
    def test_ok(self, provider_timer, dispatcher):
        ctd = ComputeTaskDef(
            task_id='test_task',
            subtask_id='test_subtask',
            performance=123
        )

        ast = TaskComputation(
            task_computer=self.task_computer, assigned_subtask=ctd,
            counting_thread=mock.Mock)
        self.task_computer.assigned_subtasks.append(ast)
        self.task_computer.finished_cb = mock.Mock()

        ast._task_finished()
        self.assertIsNone(self.task_computer.assigned_subtask_id)
        self.assertFalse(ast in self.task_computer.assigned_subtasks)
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
