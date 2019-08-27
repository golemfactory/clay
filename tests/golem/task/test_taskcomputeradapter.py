from pathlib import Path
from unittest import mock

from golem_messages.message import ComputeTaskDef
from twisted.internet import defer
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.core.statskeeper import IntStatsKeeper
from golem.task.envmanager import EnvironmentManager
from golem.task.taskcomputer import (
    NewTaskComputer,
    TaskComputer,
    TaskComputerAdapter
)
from golem.task.taskserver import TaskServer
from tests.factories.taskserver import ClientConfigDescriptor


class TaskComputerAdapterTestBase(TwistedTestCase):

    @mock.patch(
        'golem.task.taskcomputer.IntStatsKeeper', spec_set=IntStatsKeeper)
    @mock.patch('golem.task.taskcomputer.TaskComputer', spec_set=TaskComputer)
    @mock.patch(
        'golem.task.taskcomputer.NewTaskComputer', spec_set=NewTaskComputer)
    def setUp(self, new_task_computer, old_task_computer, int_stats_keeper):  # noqa pylint: disable=arguments-differ
        self.new_computer = new_task_computer()
        self.old_computer = old_task_computer()
        self.int_stats_keeper = int_stats_keeper()
        config_desc = ClientConfigDescriptor()
        config_desc.accept_tasks = True
        config_desc.in_shutdown = False
        self.task_keeper = mock.Mock()
        self.task_server = mock.Mock(
            spec=TaskServer,
            config_desc=config_desc,
            task_keeper=self.task_keeper
        )
        self.env_manager = mock.Mock(spec_set=EnvironmentManager)
        self.finished_callback = mock.Mock()
        self.adapter = TaskComputerAdapter(
            task_server=self.task_server,
            env_manager=self.env_manager,
            finished_cb=self.finished_callback
        )


class TestInit(TaskComputerAdapterTestBase):

    def test_init(self):
        self.new_computer.prepare.aseert_called_once()
        self.assertTrue(self.adapter.compute_tasks)
        self.assertTrue(self.adapter.runnable)
        self.assertIs(self.adapter.stats, self.int_stats_keeper)


class TestTaskGiven(TaskComputerAdapterTestBase):

    def test_new_computer_has_assigned_task(self):
        self.new_computer.has_assigned_task.return_value = True
        self.old_computer.has_assigned_task.return_value = False
        with self.assertRaises(AssertionError):
            self.adapter.task_given(ComputeTaskDef())

    def test_old_computer_has_assigned_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = True
        with self.assertRaises(AssertionError):
            self.adapter.task_given(ComputeTaskDef())

    def test_new_task_ok(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = False
        ctd = ComputeTaskDef(task_id='test')
        task_header = mock.Mock(environment_prerequisites=mock.Mock())
        self.task_server.task_keeper.task_headers = {
            'test': task_header
        }
        self.adapter.task_given(ctd)
        self.new_computer.task_given.assert_called_once_with(task_header, ctd)
        self.old_computer.task_given.assert_not_called()

    def test_old_task_ok(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = False
        ctd = ComputeTaskDef(task_id='test')
        task_header = mock.Mock(environment_prerequisites=None)
        self.task_server.task_keeper.task_headers = {
            'test': task_header
        }
        self.adapter.task_given(ctd)
        self.new_computer.task_given.assert_not_called()
        self.old_computer.task_given.assert_called_once_with(ctd)


class TestHasAssignedTask(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = False
        self.assertFalse(self.adapter.has_assigned_task())

    def test_assigned_new_task(self):
        self.new_computer.has_assigned_task.return_value = True
        self.old_computer.has_assigned_task.return_value = False
        self.assertTrue(self.adapter.has_assigned_task())

    def test_assigned_old_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = True
        self.assertTrue(self.adapter.has_assigned_task())


class TestAssignedTaskId(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.new_computer.assigned_task_id = None
        self.old_computer.assigned_task_id = None
        self.assertIsNone(self.adapter.assigned_task_id)

    def test_assigned_new_task(self):
        self.new_computer.assigned_task_id = 'new_task'
        self.old_computer.assigned_task_id = None
        self.assertEqual(self.adapter.assigned_task_id, 'new_task')

    def test_assigned_old_task(self):
        self.new_computer.assigned_task_id = None
        self.old_computer.assigned_task_id = 'old_task'
        self.assertEqual(self.adapter.assigned_task_id, 'old_task')


class TestAssignedSubtaskId(TaskComputerAdapterTestBase):

    def test_no_assigned_subtask(self):
        self.new_computer.assigned_subtask_id = None
        self.old_computer.assigned_subtask_id = None
        self.assertIsNone(self.adapter.assigned_subtask_id)

    def test_assigned_new_subtask(self):
        self.new_computer.assigned_subtask_id = 'new_subtask'
        self.old_computer.assigned_subtask_id = None
        self.assertEqual(self.adapter.assigned_subtask_id, 'new_subtask')

    def test_assigned_old_subtask(self):
        self.new_computer.assigned_subtask_id = None
        self.old_computer.assigned_subtask_id = 'old_subtask'
        self.assertEqual(self.adapter.assigned_subtask_id, 'old_subtask')


class TestStartComputation(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = False
        with self.assertRaises(RuntimeError):
            self.adapter.start_computation()

    @mock.patch('golem.task.taskcomputer.TaskComputerAdapter.'
                '_handle_computation_results')
    def test_assigned_new_task(self, handle_results):
        self.new_computer.has_assigned_task.return_value = True
        self.old_computer.has_assigned_task.return_value = False
        self.new_computer.assigned_task_id = 'test_task'
        self.new_computer.assigned_subtask_id = 'test_subtask'

        self.adapter.start_computation()

        self.new_computer.compute.assert_called_once()
        self.old_computer.start_computation.assert_not_called()
        self.task_keeper.task_started.assert_called_once_with('test_task')
        handle_results.assert_called_once_with(
            'test_task',
            'test_subtask',
            self.new_computer.compute())

    @mock.patch('golem.task.taskcomputer.TaskComputerAdapter.'
                '_handle_computation_results')
    def test_assigned_old_task(self, handle_results):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = True

        self.adapter.start_computation()

        self.new_computer.compute.assert_not_called()
        self.old_computer.start_computation.assert_called_once()
        handle_results.assert_not_called()


class TestHandleComputationResults(TaskComputerAdapterTestBase):

    @defer.inlineCallbacks
    def test_ok(self):
        output_file = mock.Mock()
        yield self.adapter._handle_computation_results(
            task_id='test_task',
            subtask_id='test_subtask',
            computation=defer.succeed(output_file)
        )
        self.task_server.send_task_failed.assert_not_called()
        self.task_server.send_results.assert_called_once_with(
            task_id='test_task',
            subtask_id='test_subtask',
            task_api_result=output_file,
        )
        self.finished_callback.assert_called_once_with()

    @defer.inlineCallbacks
    def test_error(self):
        error = RuntimeError('test_error')
        yield self.adapter._handle_computation_results(
            task_id='test_task',
            subtask_id='test_subtask',
            computation=defer.fail(error)
        )
        self.task_server.send_task_failed.assert_called_once_with(
            task_id='test_task',
            subtask_id='test_subtask',
            err_msg='test_error'
        )
        self.task_server.send_results.assert_not_called()
        self.finished_callback.assert_called_once_with()


class TestTaskInterrupted(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = False
        with self.assertRaises(RuntimeError):
            self.adapter.task_interrupted()

    def test_assigned_new_task(self):
        self.new_computer.has_assigned_task.return_value = True
        self.old_computer.has_assigned_task.return_value = False
        self.adapter.task_interrupted()
        self.new_computer.task_interrupted.assert_called_once()
        self.old_computer.task_interrupted.assert_not_called()

    def test_assigned_old_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = True
        self.adapter.task_interrupted()
        self.new_computer.task_interrupted.assert_not_called()
        self.old_computer.task_interrupted.assert_called_once()


class TestCheckTimeout(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.old_computer.has_assigned_task.return_value = False
        self.adapter.check_timeout()
        self.old_computer.check_timeout.assert_not_called()

    def test_assigned_task(self):
        self.old_computer.has_assigned_task.return_value = True
        self.adapter.check_timeout()
        self.old_computer.check_timeout.assert_called_once()


class TestGetProgress(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.old_computer.has_assigned_task.return_value = False
        self.assertIsNone(self.adapter.get_progress())

    def test_assigned_old_task(self):
        self.old_computer.has_assigned_task.return_value = True
        self.assertIs(
            self.adapter.get_progress(),
            self.old_computer.get_progress()
        )


class TestGetEnvironment(TaskComputerAdapterTestBase):

    def test_no_assigned_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = False
        self.assertIsNone(self.adapter.get_environment())

    def test_assigned_new_task(self):
        self.new_computer.has_assigned_task.return_value = True
        self.old_computer.has_assigned_task.return_value = False
        self.assertIs(
            self.adapter.get_environment(),
            self.new_computer.get_current_computing_env()
        )

    def test_assigned_old_task(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = True
        self.assertIs(
            self.adapter.get_environment(),
            self.old_computer.get_environment()
        )


class TestLockConfig(TaskComputerAdapterTestBase):

    def test_on(self):
        listener = mock.MagicMock()
        self.adapter.register_listener(listener)
        self.adapter.runnable = True

        self.adapter.lock_config(True)
        listener.lock_config.assert_called_once_with(True)
        self.assertFalse(self.adapter.runnable)

    def test_off(self):
        listener = mock.MagicMock()
        self.adapter.register_listener(listener)
        self.adapter.runnable = False

        self.adapter.lock_config(False)
        listener.lock_config.assert_called_once_with(False)
        self.assertTrue(self.adapter.runnable)


class TestChangeConfig(TaskComputerAdapterTestBase):

    @defer.inlineCallbacks
    def _test_compute_tasks(self, accept_tasks, in_shutdown, expected):
        self.task_server.get_task_computer_root.return_value = '/test'
        config_desc = ClientConfigDescriptor()
        config_desc.accept_tasks = accept_tasks
        config_desc.in_shutdown = in_shutdown

        yield self.adapter.change_config(config_desc)
        self.assertEqual(self.adapter.compute_tasks, expected)

    @defer.inlineCallbacks
    def test_compute_tasks_setting(self):
        yield self._test_compute_tasks(
            accept_tasks=True,
            in_shutdown=True,
            expected=False
        )
        yield self._test_compute_tasks(
            accept_tasks=True,
            in_shutdown=False,
            expected=True
        )
        yield self._test_compute_tasks(
            accept_tasks=False,
            in_shutdown=True,
            expected=False
        )
        yield self._test_compute_tasks(
            accept_tasks=False,
            in_shutdown=False,
            expected=False
        )

    @defer.inlineCallbacks
    def test_both_computers_reconfigured(self):
        config_desc = ClientConfigDescriptor()
        self.task_server.get_task_computer_root.return_value = '/test'
        yield self.adapter.change_config(config_desc)
        self.new_computer.change_config.assert_called_once_with(
            config_desc=config_desc,
            work_dir=Path('/test')
        )
        self.old_computer.change_config.assert_called_once_with(
            config_desc=config_desc,
            in_background=True
        )


class TestTaskResourcesDir(TaskComputerAdapterTestBase):
    def test_old_assigned(self):
        self.new_computer.has_assigned_task.return_value = False
        self.old_computer.has_assigned_task.return_value = True
        with self.assertRaisesRegex(
            ValueError,
            'Task resources directory only available when a task-api task'
                ' is assigned'):  # pylint: disable=bad-continuation
            self.adapter.get_task_resources_dir()

    def test_new_assigned(self):
        self.new_computer.has_assigned_task.return_value = True
        self.old_computer.has_assigned_task.return_value = False
        self.assertEqual(
            self.new_computer.get_task_resources_dir.return_value,
            self.adapter.get_task_resources_dir(),
        )


class TestQuit(TaskComputerAdapterTestBase):

    def test_quit(self):
        self.adapter.quit()
        self.new_computer.clean_up.assert_called_once()
        self.old_computer.quit.assert_called_once()
