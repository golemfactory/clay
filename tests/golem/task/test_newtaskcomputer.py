# pylint: disable=protected-access
import asyncio
import time
from pathlib import Path
from unittest import mock

from golem_messages.message import ComputeTaskDef
from golem_task_api import TaskApiService
from twisted.internet import defer
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import install_reactor
from golem.core.statskeeper import IntStatsKeeper
from golem.envs import Runtime
from golem.envs.docker.cpu import DockerCPUEnvironment, DockerCPUConfig
from golem.task.envmanager import EnvironmentManager
from golem.task.taskcomputer import NewTaskComputer
from golem.tools.testwithreactor import uninstall_reactor


class NewTaskComputerTestBase(TwistedTestCase):

    @mock.patch('golem.task.taskcomputer.ProviderAppClient')
    def setUp(self, provider_client):  # pylint: disable=arguments-differ
        self.env_manager = mock.Mock(spec=EnvironmentManager)
        self.task_finished_callback = mock.Mock()
        self.stats_keeper = mock.Mock(spec=IntStatsKeeper)
        self.provider_client = provider_client()
        self.work_dir = Path('test')
        self.task_computer = NewTaskComputer(
            env_manager=self.env_manager,
            work_dir=self.work_dir,
            task_finished_callback=self.task_finished_callback,
            stats_keeper=self.stats_keeper
        )

    @property
    def task_id(self):
        return 'test_task'

    @property
    def subtask_id(self):
        return 'test_subtask'

    @property
    def subtask_params(self):
        return {'test_param': 'test_value'}

    @property
    def env_id(self):
        return 'test_env'

    @property
    def prereq_dict(self):
        return {'test_prereq': 'test_value'}

    @property
    def performance(self):
        return 2137

    @property
    def subtask_timeout(self):
        return 3600

    @property
    def task_deadline(self):
        return int(time.time()) + 3600

    @property
    def subtask_deadline(self):
        return int(time.time()) + 3600

    def _get_task_header(self, **kwargs):
        return mock.Mock(
            task_id=kwargs.get('task_id') or self.task_id,
            environment=kwargs.get('env_id') or self.env_id,
            environment_prerequisites=(
                kwargs.get('prereq_dict') or self.prereq_dict),
            subtask_timeout=(
                kwargs.get('subtask_timeout') or self.subtask_timeout),
            deadline=kwargs.get('task_deadline') or self.task_deadline
        )

    def _get_compute_task_def(self, **kwargs):
        return ComputeTaskDef(
            subtask_id=kwargs.get('subtask_id') or self.subtask_id,
            extra_data=kwargs.get('subtask_params') or self.subtask_params,
            performance=kwargs.get('performance') or self.performance,
            deadline=kwargs.get('subtask_deadline') or self.subtask_deadline
        )

    def _patch_async(self, name, *args, **kwargs):
        patcher = mock.patch(f'golem.task.taskcomputer.{name}', *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _assign_task(self, **kwargs):
        task_header = self._get_task_header(**kwargs)
        compute_task_def = self._get_compute_task_def(**kwargs)
        self.task_computer.task_given(task_header, compute_task_def)


class TestPrepare(NewTaskComputerTestBase):

    @defer.inlineCallbacks
    def test_prepare(self):
        yield self.task_computer.prepare()
        self.env_manager.environment.assert_called_once_with(
            DockerCPUEnvironment.ENV_ID)
        self.env_manager.environment().prepare.assert_called_once()


class TestCleanUp(NewTaskComputerTestBase):

    @defer.inlineCallbacks
    def test_clean_up(self):
        yield self.task_computer.clean_up()
        self.env_manager.environment.assert_called_once_with(
            DockerCPUEnvironment.ENV_ID)
        self.env_manager.environment().clean_up.assert_called_once()


@mock.patch('golem.task.taskcomputer.ProviderTimer')
class TestTaskGiven(NewTaskComputerTestBase):

    def test_ok(self, provider_timer):
        self.assertFalse(self.task_computer.has_assigned_task())
        self.assertIsNone(self.task_computer.assigned_task_id)
        self.assertIsNone(self.task_computer.assigned_subtask_id)
        self.assertIsNone(self.task_computer.get_current_computing_env())

        task_header = self._get_task_header()
        compute_task_def = self._get_compute_task_def()
        self.task_computer.task_given(task_header, compute_task_def)

        self.assertTrue(self.task_computer.has_assigned_task())
        self.assertEqual(self.task_computer.assigned_task_id, self.task_id)
        self.assertEqual(
            self.task_computer.assigned_subtask_id,
            self.subtask_id)
        self.assertEqual(
            self.task_computer.get_current_computing_env(),
            self.env_id)
        provider_timer.start.assert_called_once_with()

    def test_has_assigned_task(self, provider_timer):
        task_header = self._get_task_header()
        compute_task_def = self._get_compute_task_def()
        self.task_computer.task_given(task_header, compute_task_def)
        provider_timer.reset_mock()
        with self.assertRaises(AssertionError):
            self.task_computer.task_given(task_header, compute_task_def)
        provider_timer.start.assert_not_called()


class TestCompute(NewTaskComputerTestBase):

    @classmethod
    def setUpClass(cls):
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        install_reactor()

    @classmethod
    def tearDownClass(cls) -> None:
        uninstall_reactor()
        asyncio.set_event_loop(None)

    def setUp(self):  # pylint: disable=arguments-differ
        super().setUp()
        self.runtime = mock.Mock(spec_set=Runtime)
        self.task_api_service = mock.Mock(
            spec=TaskApiService,
            _runtime=self.runtime
        )
        self._patch_async(
            'NewTaskComputer._get_task_api_service',
            return_value=self.task_api_service
        )
        self.task_dir = Path('task_dir')
        self._patch_async(
            'NewTaskComputer._get_task_dir',
            return_value=self.task_dir
        )
        self.provider_timer = self._patch_async('ProviderTimer')
        self.dispatcher = self._patch_async('dispatcher')
        self.logger = self._patch_async('logger')

    @defer.inlineCallbacks
    def test_no_assigned_task(self):
        with self.assertRaises(AssertionError):
            yield self.task_computer.compute()

    @defer.inlineCallbacks
    def test_ok(self):
        self._assign_task()
        future = asyncio.Future()
        future.set_result('result.txt')
        self.provider_client.compute.return_value = future

        result = yield self.task_computer.compute()

        self.assertEqual(result, self.task_dir / 'result.txt')
        self.stats_keeper.increase_stat.assert_called_once_with(
            'computed_tasks')
        self.dispatcher.send.assert_has_calls((
            mock.call(
                signal='golem.taskcomputer',
                event='subtask_finished',
                subtask_id=self.subtask_id,
                min_performance=self.performance,
            ), mock.call(
                signal='golem.monitor',
                event='computation_time_spent',
                success=True,
                value=self.subtask_timeout
            )
        ), any_order=True)
        self.provider_timer.finish.assert_called_once()
        self.task_finished_callback.assert_called_once()
        self.assertFalse(self.task_computer.has_assigned_task())

    @defer.inlineCallbacks
    def test_task_interrupted(self):
        self._assign_task()
        self.provider_client.compute.return_value = asyncio.Future()

        deferred = self.task_computer.compute()
        self.task_computer.task_interrupted()
        result = yield deferred

        self.assertIsNone(result)
        self.logger.warning.assert_called_once()
        self.stats_keeper.increase_stat.assert_not_called()
        self.dispatcher.send.assert_has_calls((
            mock.call(
                signal='golem.taskcomputer',
                event='subtask_finished',
                subtask_id=self.subtask_id,
                min_performance=self.performance,
            ), mock.call(
                signal='golem.monitor',
                event='computation_time_spent',
                success=False,
                value=self.subtask_timeout
            )
        ), any_order=True)
        self.provider_timer.finish.assert_called_once()
        self.task_finished_callback.assert_called_once()
        self.assertFalse(self.task_computer.has_assigned_task())

    @defer.inlineCallbacks
    def test_task_timed_out(self):
        # Subtask deadline already passed
        self._assign_task(subtask_deadline=time.time())
        self.provider_client.compute.return_value = asyncio.sleep(10)

        result = yield self.task_computer.compute()

        self.assertIsNone(result)
        self.logger.error.assert_called_once()
        self.stats_keeper.increase_stat.assert_called_once_with(
            'tasks_with_timeout')
        self.dispatcher.send.assert_has_calls((
            mock.call(
                signal='golem.taskcomputer',
                event='subtask_finished',
                subtask_id=self.subtask_id,
                min_performance=self.performance,
            ), mock.call(
                signal='golem.monitor',
                event='computation_time_spent',
                success=False,
                value=self.subtask_timeout
            )
        ), any_order=True)
        self.provider_timer.finish.assert_called_once()
        self.task_finished_callback.assert_called_once()
        self.assertFalse(self.task_computer.has_assigned_task())

    @defer.inlineCallbacks
    def test_task_error(self):
        self._assign_task()
        future = asyncio.Future()
        future.set_exception(OSError)
        self.provider_client.compute.return_value = future

        with self.assertRaises(OSError):
            yield self.task_computer.compute()

        self.logger.exception.assert_called_once()
        self.stats_keeper.increase_stat.assert_called_once_with(
            'tasks_with_errors')
        self.dispatcher.send.assert_has_calls((
            mock.call(
                signal='golem.taskcomputer',
                event='subtask_finished',
                subtask_id=self.subtask_id,
                min_performance=self.performance,
            ), mock.call(
                signal='golem.monitor',
                event='computation_time_spent',
                success=False,
                value=self.subtask_timeout
            )
        ), any_order=True)
        self.provider_timer.finish.assert_called_once()
        self.task_finished_callback.assert_called_once()
        self.assertFalse(self.task_computer.has_assigned_task())


class TestGetTaskApiService(NewTaskComputerTestBase):

    @mock.patch('golem.task.taskcomputer.EnvironmentTaskApiService')
    def test_get_task_api_service(self, env_task_api_service):
        self._assign_task()
        service = self.task_computer._get_task_api_service()
        self.env_manager.environment.assert_called_once_with(self.env_id)
        self.env_manager.payload_builder.assert_called_once_with(self.env_id)
        self.env_manager.environment().parse_prerequisites\
            .assert_called_once_with(self.prereq_dict)

        self.assertEqual(service, env_task_api_service.return_value)
        env_task_api_service.assert_called_once_with(
            env=self.env_manager.environment(),
            prereq=self.env_manager.environment().parse_prerequisites(),
            shared_dir=self.work_dir / self.env_id / self.task_id,
            payload_builder=self.env_manager.payload_builder()
        )


class TestChangeConfig(NewTaskComputerTestBase):

    @defer.inlineCallbacks
    def test_computation_running(self):
        self.task_computer._computation = mock.Mock()
        work_dir = Path('test_dir')
        config_desc = ClientConfigDescriptor()
        with self.assertRaises(AssertionError):
            yield self.task_computer.change_config(config_desc, work_dir)

    @defer.inlineCallbacks
    def test_ok(self):
        work_dir = Path('test_dir')
        config_desc = ClientConfigDescriptor()
        config_desc.num_cores = 13
        config_desc.max_memory_size = 1024 * 1024

        yield self.task_computer.change_config(config_desc, work_dir)

        self.assertEqual(self.task_computer._work_dir, work_dir)
        self.env_manager.environment.assert_called_once_with(
            DockerCPUEnvironment.ENV_ID)
        self.env_manager.environment().update_config.assert_called_once_with(
            DockerCPUConfig(
                work_dirs=[Path('test_dir')],
                cpu_count=13,
                memory_mb=1024,
            )
        )
