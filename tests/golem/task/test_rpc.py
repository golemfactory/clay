# pylint: disable=protected-access,too-many-ancestors
import copy
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
import uuid

import faker
from ethereum.utils import denoms
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from mock import Mock
from twisted.internet import defer

from apps.dummy.task import dummytaskstate
from apps.dummy.task.dummytask import DummyTask
from apps.rendering.task.renderingtask import RenderingTask
from golem import clientconfigdescriptor
from golem.core import common
from golem.core import deferred as golem_deferred
from golem.ethereum import exceptions
from golem.network.p2p import p2pservice
from golem.task import rpc
from golem.task import taskbase
from golem.task import taskserver
from golem.task import taskstate
from golem.task import tasktester
from golem.task.rpc import ClientProvider
from tests.golem import test_client
from tests.golem.test_client import TestClientBase

fake = faker.Faker()
task_output_path = TemporaryDirectory(prefix='golem-test-output-').name


class ProviderBase(test_client.TestClientBase):
    maxDiff = None
    T_DICT = {
        'compute_on': 'cpu',
        'resources': [
            '/Users/user/Desktop/folder/texture.tex',
            '/Users/user/Desktop/folder/model.mesh',
            '/Users/user/Desktop/folder/stylized_levi.blend'
        ],
        'name': fake.pystr(min_chars=4, max_chars=24),
        'type': 'blender',
        'timeout': '09:25:00',
        'subtasks_count': 6,
        'subtask_timeout': '4:10:00',
        'bid': '0.000032',
        'options': {
            'resolution': [1920, 1080],
            'frames': '1-10',
            'format': 'EXR',
            'output_path': task_output_path,
            'compositing': True,
        },
        'concent_enabled': False,
    }

    def setUp(self):
        super().setUp()
        self.client.sync = mock.Mock()
        self.client.p2pservice = mock.Mock(peers={})
        self.client.apps_manager._benchmark_enabled = mock.Mock(
            return_value=True
        )
        self.client.apps_manager.load_all_apps()
        with mock.patch(
            'golem.network.concent.handlers_library.HandlersLibrary'
            '.register_handler',
        ):
            self.client.task_server = taskserver.TaskServer(
                node=dt_p2p_factory.Node(),
                config_desc=clientconfigdescriptor.ClientConfigDescriptor(),
                client=self.client,
                use_docker_manager=False,
                apps_manager=self.client.apps_manager,
            )
        self.client.monitor = mock.Mock()

        self.provider = rpc.ClientProvider(self.client)
        self.t_dict = copy.deepcopy(self.T_DICT)
        self.client.resource_server = mock.Mock()

        def create_resource_package(*_args):
            result = 'package_path', 'package_sha1'
            return test_client.done_deferred(result)

        def add_resources(*_args, **_kwargs):
            resource_manager_result = 'res_hash', ['res_file_1']
            result = resource_manager_result, 'res_file_1', 'package_hash', 42
            return test_client.done_deferred(result)

        self.client.resource_server.create_resource_package = mock.Mock(
            side_effect=create_resource_package)
        self.client.resource_server.add_resources = mock.Mock(
            side_effect=add_resources)

        def add_new_task(task, *_args, **_kwargs):
            instance = self.client.task_manager
            instance.tasks_states[task.header.task_id] = taskstate.TaskState()
            instance.tasks[task.header.task_id] = task
        self.client.task_server.task_manager.start_task = lambda tid: tid
        self.client.task_server.task_manager.add_new_task = add_new_task


@mock.patch('signal.signal')
@mock.patch('golem.network.p2p.local_node.LocalNode.collect_network_info')
@mock.patch('golem.task.rpc.enqueue_new_task')
@mock.patch(
    'golem.task.taskmanager.TaskManager.create_task',
    side_effect=lambda *_: mock.MagicMock(
        header=mock.MagicMock(task_id='task_id'),
    ),
)
class TestCreateTask(ProviderBase, TestClientBase):
    @mock.patch(
        'golem.task.rpc.ClientProvider._validate_lock_funds_possibility'
    )
    def test_create_task(self, *_):
        t = dummytaskstate.DummyTaskDefinition()
        t.name = "test"

        result = self.provider.create_task(t.to_dict())
        rpc.enqueue_new_task.assert_called()
        self.assertEqual(result, ('task_id', None))

    def test_create_task_fail_on_empty_dict(self, *_):
        result = self.provider.create_task({})
        assert result == (None,
                          "Length of task name cannot be less "
                          "than 4 or more than 24 characters.")

    def test_create_task_fail_on_too_long_name(self, *_):
        result = self.provider.create_task({
            "name": "This name has 27 characters"
        })
        assert result == (None,
                          "Length of task name cannot be less "
                          "than 4 or more than 24 characters.")

    def test_create_task_fail_on_illegal_character_in_name(self, *_):
        result = self.provider.create_task({
            "name": "Golem task/"
        })
        assert result == (None,
                          "Task name can only contain letters, numbers, "
                          "spaces, underline, dash or dot.")

    @mock.patch(
        'golem.task.rpc.ClientProvider._validate_lock_funds_possibility',
        side_effect=exceptions.NotEnoughFunds.single_currency(
            required=0.166667 * denoms.ether,
            available=0,
            currency='GNT'
        ))
    def test_create_task_fail_if_not_enough_gnt_available(self, mocked, *_):
        t = dummytaskstate.DummyTaskDefinition()
        t.name = "test"

        result = self.provider.create_task(t.to_dict())

        rpc.enqueue_new_task.assert_not_called()
        self.assertIn('validate_lock_funds_possibility', str(mocked))
        mocked.assert_called()

        self.assertIsNone(result[0])
        error = result[1]
        # noqa pylint:disable=unsubscriptable-object
        self.assertEqual(error['error_type'], 'NotEnoughFunds')
        self.assertEqual(error['error_msg'], 'Not enough funds available.\n'
                                             'Required GNT: '
                                             '0.166667, available: 0.000000\n')


class ConcentDepositLockPossibilityTest(unittest.TestCase):

    def test_validate_lock_funds_possibility_raises_if_not_enough_funds(self):
        available_gnt = 0.0001 * denoms.ether
        required_gnt = 0.0005 * denoms.ether
        available_eth = 0.0002 * denoms.ether
        required_eth = 0.0006 * denoms.ether
        client = Mock()
        client.transaction_system.get_available_gnt.return_value = available_gnt
        client.transaction_system.get_available_eth.return_value = available_eth
        client.transaction_system.eth_for_batch_payment.return_value = \
            required_eth
        client_provider = ClientProvider(client)

        with self.assertRaises(exceptions.NotEnoughFunds) as e:
            client_provider._validate_lock_funds_possibility(
                total_price_gnt=required_gnt,
                number_of_tasks=1
            )
        expected = f'Not enough funds available.\n' \
            f'Required GNT: {required_gnt / denoms.ether:f}, ' \
            f'available: {available_gnt / denoms.ether:f}\n' \
            f'Required ETH: {required_eth / denoms.ether:f}, ' \
            f'available: {available_eth / denoms.ether:f}\n'
        self.assertIn(str(e.exception), expected)


class TestRestartTask(ProviderBase):
    @mock.patch('os.path.getsize', return_value=123)
    @mock.patch('golem.network.concent.client.ConcentClientService.start')
    @mock.patch('golem.client.SystemMonitor')
    @mock.patch('golem.client.P2PService.connect_to_network')
    def test_restart_task(self, connect_to_network, *_):
        self.client.apps_manager.load_all_apps()

        deferred = defer.Deferred()
        connect_to_network.side_effect = lambda *_: deferred.callback(True)
        self.client.are_terms_accepted = lambda: True
        self.client.start()
        golem_deferred.sync_wait(deferred)

        def create_resource_package(*_args):
            result = 'package_path', 'package_sha1'
            return test_client.done_deferred(result)

        def add_resources(*_args, **_kwargs):
            resource_manager_result = 'res_hash', ['res_file_1']
            result = resource_manager_result, 'res_file_1', 'package_hash', 0
            return test_client.done_deferred(result)

        self.client.resource_server = mock.Mock(
            create_resource_package=mock.Mock(
                side_effect=create_resource_package,
            ),
            add_resources=mock.Mock(side_effect=add_resources)
        )

        task_manager = self.client.task_server.task_manager

        task_manager.dump_task = mock.Mock()

        some_file_path = self.new_path / "foo"
        # pylint thinks it's PurePath, but it's a concrete path
        some_file_path.touch()  # pylint: disable=no-member

        task_dict = {
            'bid': 5.0,
            'compute_on': 'cpu',
            'name': 'test task',
            'options': {
                'difficulty': 1337,
                'output_path': task_output_path,
            },
            'resources': [str(some_file_path)],
            'subtask_timeout': common.timeout_to_string(3),
            'subtasks_count': 1,
            'timeout': common.timeout_to_string(3),
            'type': 'Dummy',
        }

        task = self.client.task_manager.create_task(task_dict)
        golem_deferred.sync_wait(rpc.enqueue_new_task(self.client, task))
        with mock.patch('golem.task.rpc.enqueue_new_task') as enq_mock:
            new_task_id, error = self.provider.restart_task(task.header.task_id)
            enq_mock.assert_called_once()
        assert new_task_id
        assert not error

        assert task.header.task_id != new_task_id
        assert task_manager.tasks_states[
            task.header.task_id].status == taskstate.TaskStatus.restarted
        old_subtask_states = task_manager.tasks_states[task.header.task_id] \
            .subtask_states.values()
        assert all(
            ss.subtask_status == taskstate.SubtaskStatus.restarted
            for ss
            in old_subtask_states)


class TestGetMaskForTask(test_client.TestClientBase):
    def test_get_mask_for_task(self, *_):
        def _check(  # pylint: disable=too-many-arguments
                num_tasks=0,
                network_size=0,
                mask_size_factor=1.0,
                min_num_workers=0,
                perf_rank=0.0,
                exp_desired_workers=0,
                exp_potential_workers=0):

            self.client.config_desc.initial_mask_size_factor = mask_size_factor
            self.client.config_desc.min_num_workers_for_mask = min_num_workers

            with mock.patch.object(
                self.client,
                'p2pservice',
                spec=p2pservice.P2PService
            ) as p2p, \
                    mock.patch.object(
                        self.client, 'task_server', spec=taskserver.TaskServer
                    ), \
                    mock.patch(
                        'golem_messages.datastructures.tasks.masking.Mask'
                    ) as mask:

                p2p.get_estimated_network_size.return_value = network_size
                p2p.get_performance_percentile_rank.return_value = perf_rank

                task = mock.MagicMock()
                task.get_total_tasks.return_value = num_tasks

                rpc._get_mask_for_task(self.client, task)

                mask.get_mask_for_task.assert_called_once_with(
                    desired_num_workers=exp_desired_workers,
                    potential_num_workers=exp_potential_workers
                )

        _check()

        _check(
            num_tasks=1,
            exp_desired_workers=1)

        _check(
            num_tasks=2,
            mask_size_factor=2,
            exp_desired_workers=4)

        _check(
            min_num_workers=10,
            exp_desired_workers=10)

        _check(
            num_tasks=2,
            mask_size_factor=5,
            min_num_workers=4,
            exp_desired_workers=10)

        _check(
            network_size=1,
            exp_potential_workers=1)

        _check(
            network_size=1,
            perf_rank=1,
            exp_potential_workers=0)

        _check(
            network_size=10,
            perf_rank=0.2,
            exp_potential_workers=8)


@mock.patch('os.path.getsize')
class TestEnqueueNewTask(ProviderBase):
    def test_enqueue_new_task(self, *_):
        c = self.client
        c.task_server.task_manager.key_id = 'deadbeef'
        c.p2pservice.get_estimated_network_size.return_value = 0

        task = self.client.task_manager.create_task(self.t_dict)
        deferred = rpc.enqueue_new_task(self.client, task)
        task = golem_deferred.sync_wait(deferred)
        task_id = task.header.task_id
        assert isinstance(task, taskbase.Task)
        assert task.header.task_id
        assert c.resource_server.add_resources.called

        c.task_server.task_manager.tasks[task_id] = task
        c.task_server.task_manager.tasks_states[task_id] = taskstate.TaskState()
        frames = c.task_server.task_manager.get_output_states(task_id)
        assert frames is not None

    def test_ensure_task_deposit(self, *_):
        self.client.concent_service = mock.Mock()
        self.client.concent_service.enabled = True
        self.t_dict['concent_enabled'] = True
        task = self.client.task_manager.create_task(self.t_dict)
        deferred = rpc.enqueue_new_task(self.client, task)
        golem_deferred.sync_wait(deferred)
        self.client.transaction_system.concent_deposit.assert_called_once_with(
            required=mock.ANY,
            expected=mock.ANY,
        )

    @mock.patch('golem.task.rpc.logger.error')
    @mock.patch('golem.task.rpc._ensure_task_deposit')
    def test_ethereum_error(self, deposit_mock, log_mock, *_):
        from golem.ethereum import exceptions as eth_exceptions
        deposit_mock.side_effect = eth_exceptions.EthereumError('TEST ERROR')
        task = self.client.task_manager.create_task(self.t_dict)
        deferred = rpc.enqueue_new_task(self.client, task)
        with self.assertRaises(eth_exceptions.EthereumError):
            golem_deferred.sync_wait(deferred)
        log_mock.assert_called_once()

    @mock.patch('golem.task.rpc.logger.exception')
    @mock.patch('golem.task.rpc._start_task')
    def test_general_exception(self, start_mock, log_mock, *_):
        start_mock.side_effect = RuntimeError("TEST ERROR")
        task = self.client.task_manager.create_task(self.t_dict)
        deferred = rpc.enqueue_new_task(self.client, task)
        with self.assertRaises(RuntimeError):
            golem_deferred.sync_wait(deferred)
        log_mock.assert_called_once()


@mock.patch('golem.task.rpc._run_test_task')
class TestProviderRunTestTask(ProviderBase):
    def test_no_concent_enabled_in_dict(self, run_mock, *_):
        # This used to raise KeyError before run_test_task
        del self.t_dict['concent_enabled']
        self.assertTrue(
            self.provider.run_test_task(self.t_dict),
        )
        run_mock.assert_called_once()

    def test_another_is_running(self, run_mock, *_):
        self.client.task_tester = object()
        self.assertFalse(
            self.provider.run_test_task(self.t_dict),
        )
        self.assertEqual(
            self.client.task_test_result,
            {
                "status": taskstate.TaskTestStatus.error,
                "error": "Another test is running",
            },
        )
        run_mock.assert_not_called()

    def test_positive(self, run_mock, *_):
        self.assertTrue(
            self.provider.run_test_task(self.t_dict),
        )
        run_mock.assert_called_once_with(
            client=self.client,
            task_dict=self.t_dict,
        )


class TestRuntTestTask(ProviderBase):
    def _check_task_tester_result(self):
        self.assertIsInstance(self.client.task_test_result, dict)
        self.assertEqual(self.client.task_test_result, {
            "status": taskstate.TaskTestStatus.started,
            "error": None
        })

    @mock.patch('golem.task.taskmanager.TaskManager.create_task')
    def test_run_test_task_success(self, *_):
        result = {'result': 'result'}
        estimated_memory = 1234
        time_spent = 1.234
        more = {'more': 'more'}

        def _run(_self: tasktester.TaskTester):
            self._check_task_tester_result()
            _self.success_callback(result, estimated_memory, time_spent, **more)

        with mock.patch('golem.task.tasktester.TaskTester.run', _run):
            golem_deferred.sync_wait(rpc._run_test_task(self.client, {}))

        self.assertIsInstance(self.client.task_test_result, dict)
        self.assertEqual(self.client.task_test_result, {
            "status": taskstate.TaskTestStatus.success,
            "result": result,
            "estimated_memory": estimated_memory,
            "time_spent": time_spent,
            "more": more
        })

    @mock.patch('golem.task.taskmanager.TaskManager.create_task')
    def test_run_test_task_error(self, *_):
        error = ('error', 'error')
        more = {'more': 'more'}

        def _run(_self: tasktester.TaskTester):
            self._check_task_tester_result()
            _self.error_callback(*error, **more)

        with mock.patch('golem.client.TaskTester.run', _run):
            golem_deferred.sync_wait(rpc._run_test_task(self.client, {}))

        self.assertIsInstance(self.client.task_test_result, dict)
        self.assertEqual(self.client.task_test_result, {
            "status": taskstate.TaskTestStatus.error,
            "error": error,
            "more": more
        })

    def test_run_test_task_params(self, *_):
        with mock.patch(
            'apps.blender.task.blenderrendertask.'
            'BlenderTaskTypeInfo.for_purpose',
        ),\
                mock.patch('golem.client.TaskTester.run'):
            golem_deferred.sync_wait(rpc._run_test_task(
                self.client,
                {
                    'type': 'blender',
                    'resources': ['_.blend'],
                    'subtasks_count': 1,
                }))


class TestValidateTaskDict(ProviderBase):
    def test_concent_service_disabled(self, *_):
        self.t_dict['concent_enabled'] = True
        self.client.concent_service = mock.Mock()
        self.client.concent_service.available = False
        self.client.concent_service.enabled = False

        msg = "Cannot create task with concent enabled when " \
              "Concent Service is disabled"
        with self.assertRaisesRegex(rpc.CreateTaskError, msg):
            rpc._validate_task_dict(self.client, self.t_dict)

    def test_concent_service_switched_off(self, *_):
        self.t_dict['concent_enabled'] = True
        self.client.concent_service = mock.Mock()
        self.client.concent_service.available = True
        self.client.concent_service.enabled = False

        msg = "Cannot create task with concent enabled when " \
              "Concent Service is switched off"
        with self.assertRaisesRegex(rpc.CreateTaskError, msg):
            rpc._validate_task_dict(self.client, self.t_dict)

    @mock.patch(
        "apps.rendering.task.framerenderingtask.calculate_subtasks_count",
    )
    def test_computed_subtasks(self, calculate_mock, *_):
        computed_subtasks = self.t_dict['subtasks_count'] - 1
        calculate_mock.return_value = computed_subtasks
        msg = "Subtasks count {:d} is invalid. Maybe use {:d} instead?".format(
            self.t_dict['subtasks_count'],
            computed_subtasks,
        )
        with self.assertRaisesRegex(ValueError, msg):
            rpc._validate_task_dict(self.client, self.t_dict)


@mock.patch('os.path.getsize')
@mock.patch('golem.task.taskmanager.TaskManager.dump_task')
@mock.patch("golem.task.rpc._restart_subtasks")
class TestRestartSubtasks(ProviderBase):
    def setUp(self):
        super().setUp()
        self.task = self.client.task_manager.create_task(self.t_dict)
        with mock.patch('os.path.getsize'):
            golem_deferred.sync_wait(
                rpc.enqueue_new_task(self.client, self.task),
            )

    def test_empty(self, restart_mock, *_):
        force = fake.pybool()
        self.provider.restart_subtasks_from_task(
            task_id=self.task.header.task_id,
            subtask_ids=[],
            force=force,
        )
        restart_mock.assert_called_once_with(
            client=self.client,
            subtask_ids_to_copy=set(),
            old_task_id=self.task.header.task_id,
            task_dict=mock.ANY,
            force=force,
        )


class TestRestartFrameSubtasks(ProviderBase):
    def setUp(self):
        super().setUp()
        self.task = self.client.task_manager.create_task(self.t_dict)
        with mock.patch('os.path.getsize'):
            golem_deferred.sync_wait(
                rpc.enqueue_new_task(self.client, self.task),
            )

    @mock.patch('golem.task.rpc.ClientProvider.restart_subtasks_from_task')
    @mock.patch('golem.client.Client.restart_subtask')
    def test_no_frames(self, mock_restart_single, mock_restart_multiple, *_):
        with mock.patch(
            'golem.task.taskmanager.TaskManager.get_frame_subtasks',
            return_value=None
        ):
            self.provider.restart_frame_subtasks(
                task_id=self.task.header.task_id,
                frame=1
            )

        mock_restart_single.assert_not_called()
        mock_restart_multiple.assert_not_called()

    @mock.patch('golem.task.taskstate.TaskStatus.is_active', return_value=True)
    @mock.patch('golem.task.rpc.ClientProvider.restart_subtasks_from_task')
    @mock.patch('golem.client.Client.restart_subtask')
    def test_task_active(self, mock_restart_single, mock_restart_multiple, *_):
        mock_subtask_id_1 = 'mock-subtask-id-1'
        mock_subtask_id_2 = 'mock-subtask-id-2'
        mock_frame_subtasks = {
            mock_subtask_id_1: Mock(),
            mock_subtask_id_2: Mock()
        }

        with mock.patch(
            'golem.task.taskmanager.TaskManager.get_frame_subtasks',
            return_value=mock_frame_subtasks
        ):
            self.provider.restart_frame_subtasks(
                task_id=self.task.header.task_id,
                frame=1
            )

        mock_restart_multiple.assert_not_called()
        mock_restart_single.assert_has_calls(
            [mock.call(mock_subtask_id_1), mock.call(mock_subtask_id_2)]
        )

    @mock.patch('golem.task.taskstate.TaskStatus.is_active', return_value=False)
    @mock.patch('golem.task.rpc.ClientProvider.restart_subtasks_from_task')
    @mock.patch('golem.client.Client.restart_subtask')
    def test_task_finished(
            self, mock_restart_single, mock_restart_multiple, *_):
        mock_subtask_id_1 = 'mock-subtask-id-1'
        mock_subtask_id_2 = 'mock-subtask-id-2'
        mock_frame_subtasks = {
            mock_subtask_id_1: Mock(),
            mock_subtask_id_2: Mock()
        }

        with mock.patch(
            'golem.task.taskmanager.TaskManager.get_frame_subtasks',
            return_value=mock_frame_subtasks
        ):
            self.provider.restart_frame_subtasks(
                task_id=self.task.header.task_id,
                frame=1
            )

        mock_restart_single.assert_not_called()
        mock_restart_multiple.assert_called_once_with(
            self.task.header.task_id,
            mock_frame_subtasks.keys()
        )

    @mock.patch('golem.task.rpc.ClientProvider.restart_subtasks_from_task')
    @mock.patch('golem.client.Client.restart_subtask')
    @mock.patch('golem.task.rpc.logger')
    def test_task_unknown(
            self,
            mock_logger,
            mock_restart_single,
            mock_restart_multiple,
            *_):
        mock_subtask_id_1 = 'mock-subtask-id-1'
        mock_subtask_id_2 = 'mock-subtask-id-2'
        mock_frame_subtasks = {
            mock_subtask_id_1: Mock(),
            mock_subtask_id_2: Mock()
        }

        with mock.patch(
            'golem.task.taskmanager.TaskManager.get_frame_subtasks',
            return_value=mock_frame_subtasks
        ):
            self.provider.restart_frame_subtasks(
                task_id='unknown-task-id',
                frame=1
            )

        mock_logger.error.assert_called_once()
        mock_restart_single.assert_not_called()
        mock_restart_multiple.assert_not_called()


@mock.patch('os.path.getsize')
class TestExceptionPropagation(ProviderBase):
    def setUp(self):
        super().setUp()
        self.task = self.client.task_manager.create_task(self.t_dict)
        with mock.patch('os.path.getsize'):
            golem_deferred.sync_wait(
                rpc.enqueue_new_task(self.client, self.task),
            )

    @mock.patch("golem.task.rpc.prepare_and_validate_task_dict")
    def test_create_task(self, mock_method, *_):
        t = dummytaskstate.DummyTaskDefinition()
        t.name = "test"
        mock_method.side_effect = Exception("Test")

        result = self.provider.create_task(t.to_dict())
        mock_method.assert_called()
        self.assertEqual(result, (None, "Test"))

    def test_restart_task(self, *_):
        t = dummytaskstate.DummyTaskDefinition()
        t.name = "test"

        self.provider.task_manager.assert_task_can_be_restarted =\
            mock.MagicMock()
        self.provider.task_manager.assert_task_can_be_restarted\
            .side_effect = Exception("Test")

        result = self.provider.restart_task(0)

        self.assertEqual(result, (None, "Test"))

    @mock.patch("golem.task.rpc.prepare_and_validate_task_dict")
    def test_run_test_task_error(self, mock_method, *_):
        t = dummytaskstate.DummyTaskDefinition()
        t.name = "test"
        mock_method.side_effect = Exception("Test")

        result = self.provider.run_test_task(t.to_dict())
        mock_method.assert_called()
        self.assertEqual(result, False)


class TestGetEstimatedCost(ProviderBase):
    def setUp(self):
        super().setUp()
        self.transaction_system = ts = self.client.transaction_system
        ts.eth_for_batch_payment.return_value = 10000
        ts.eth_for_deposit.return_value = 20000

    def test_basic(self, *_):
        subtasks = 5
        result = self.provider.get_estimated_cost(
            "task type",
            {
                "price": '150',
                "subtask_timeout": '00:00:02',
                "subtasks_count": str(subtasks),
            },
        )
        self.assertEqual(
            result,
            {
                "GNT": '5',
                'ETH': '10000',
                'deposit': {
                    'GNT_required': '10',
                    'GNT_suggested': '20',
                    'ETH': '20000',
                },
            },
        )
        self.transaction_system.eth_for_batch_payment.assert_called_once_with(
            subtasks,
        )
        self.transaction_system.eth_for_deposit.assert_called_once_with()


@mock.patch('golem.task.taskmanager.TaskManager.get_subtask_dict',
            return_value=Mock())
class TestGetFragments(ProviderBase):

    def test_get_fragments(self, *_):
        task_id = str(uuid.uuid4())
        subtasks_count = 3
        mock_task = Mock(spec=RenderingTask)
        mock_task.total_tasks = subtasks_count
        mock_task.subtasks_given = {
            'subtask-uuid-1': {
                'subtask_id': 'subtask-uuid-1',
                'start_task': 1,
            },
            'subtask-uuid-2': {
                'subtask_id': 'subtask-uuid-2',
                'start_task': 2,
            },
            'subtask-uuid-3': {
                'subtask_id': 'subtask-uuid-3',
                'start_task': 2,
            },
            'subtask-uuid-4': {
                'subtask_id': 'subtask-uuid-4',
                'start_task': 2,
            },
        }
        self.client.task_server.task_manager.tasks[task_id] = mock_task

        task_fragments, error = self.provider.get_fragments(task_id)

        self.assertTrue(len(task_fragments) == subtasks_count)
        self.assertTrue(len(task_fragments[1]) == 1)
        self.assertTrue(len(task_fragments[2]) == 3)
        self.assertTrue(len(task_fragments[3]) == 0)

    def test_task_not_found(self, *_):
        task_id = str(uuid.uuid4())

        task_fragments, error = self.provider.get_fragments(task_id)

        self.assertIsNone(task_fragments)
        self.assertTrue('Task not found' in error)

    def test_wrong_task_type(self, *_):
        task_id = str(uuid.uuid4())
        mock_task = Mock(spec=DummyTask)
        self.client.task_server.task_manager.tasks[task_id] = mock_task

        task_fragments, error = self.provider.get_fragments(task_id)

        self.assertIsNone(task_fragments)
        self.assertTrue('Incorrect task type' in error)
