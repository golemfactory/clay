# pylint: disable=protected-access,too-many-ancestors
import copy
from unittest import mock

import faker
from twisted.internet import defer

from apps.dummy.task import dummytaskstate
from golem import clientconfigdescriptor
from golem.core import common
from golem.core import deferred as golem_deferred
from golem.network.p2p import node as p2p_node
from golem.network.p2p import p2pservice
from golem.task import rpc
from golem.task import taskbase
from golem.task import taskserver
from golem.task import taskstate
from golem.task import tasktester
from tests.golem import test_client


fake = faker.Faker()


class ProviderBase(test_client.TestClientBase):
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
                node=p2p_node.Node(),
                config_desc=clientconfigdescriptor.ClientConfigDescriptor(),
                client=self.client,
                use_docker_manager=False,
                apps_manager=self.client.apps_manager,
            )
        self.client.monitor = mock.Mock()

        self.provider = rpc.ClientProvider(self.client)


mock_task = mock.MagicMock()
mock_task.header.task_id = 'task_id'


@mock.patch('signal.signal')
@mock.patch('golem.network.p2p.node.Node.collect_network_info')
@mock.patch('golem.task.rpc.enqueue_new_task')
@mock.patch(
    'golem.task.taskmanager.TaskManager.create_task',
    return_value=mock_task,
)
class TestCreateTask(ProviderBase):
    def test_create_task(self, *_):
        t = dummytaskstate.DummyTaskDefinition()
        t.task_name = "test"

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


class TestRestartTask(ProviderBase):
    @mock.patch('os.path.getsize')
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

        def add_task(*_args, **_kwargs):
            resource_manager_result = 'res_hash', ['res_file_1']
            result = resource_manager_result, 'res_file_1', 'package_hash', 0
            return test_client.done_deferred(result)

        self.client.resource_server = mock.Mock(
            create_resource_package=mock.Mock(
                side_effect=create_resource_package,
            ),
            add_task=mock.Mock(side_effect=add_task)
        )

        task_manager = self.client.task_server.task_manager

        task_manager.dump_task = mock.Mock()
        task_manager.listen_address = '127.0.0.1'
        task_manager.listen_port = 40103

        some_file_path = self.new_path / "foo"
        # pylint thinks it's PurePath, but it's a concrete path
        some_file_path.touch()  # pylint: disable=no-member

        task_dict = {
            'bid': 5.0,
            'compute_on': 'cpu',
            'name': 'test task',
            'options': {
                'difficulty': 1337,
                'output_path': '',
            },
            'resources': [str(some_file_path)],
            'subtask_timeout': common.timeout_to_string(3),
            'subtasks': 1,
            'timeout': common.timeout_to_string(3),
            'type': 'Dummy',
        }

        task_id, error = self.provider.create_task(task_dict)

        assert task_id
        assert not error

        new_task_id, error = self.provider.restart_task(task_id)
        assert new_task_id
        assert not error
        assert len(task_manager.tasks_states) == 2

        assert task_id != new_task_id
        assert task_manager.tasks_states[
            task_id].status == taskstate.TaskStatus.restarted
        assert all(
            ss.subtask_status == taskstate.SubtaskStatus.restarted
            for ss
            in task_manager.tasks_states[task_id].subtask_states.values())
        assert task_manager.tasks_states[new_task_id].status \
            == taskstate.TaskStatus.waiting


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
                    mock.patch('golem.task.masking.Mask') as mask:

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


class TestEnqueueNewTask(ProviderBase):
    T_DICT = {
        'compute_on': 'cpu',
        'resources': [
            '/Users/user/Desktop/folder/texture.tex',
            '/Users/user/Desktop/folder/model.mesh',
            '/Users/user/Desktop/folder/stylized_levi.blend'
        ],
        'name': 'Golem Task 17:41:45 GMT+0200 (CEST)',
        'type': 'blender',
        'timeout': '09:25:00',
        'subtasks': '6',
        'subtask_timeout': '4:10:00',
        'bid': '0.000032',
        'options': {
            'resolution': [1920, 1080],
            'frames': '1-10',
            'format': 'EXR',
            'output_path': '/Users/user/Desktop/',
            'compositing': True,
        }
    }

    def setUp(self):
        super().setUp()
        self.t_dict = copy.deepcopy(self.T_DICT)

    @mock.patch('os.path.getsize')
    def test_enqueue_new_task(self, *_):
        def add_new_task(task, *_args, **_kwargs):
            instance = self.client.task_manager
            instance.tasks_states[task.header.task_id] = taskstate.TaskState()

        def create_resource_package(*_args):
            result = 'package_path', 'package_sha1'
            return test_client.done_deferred(result)

        def add_task(*_args, **_kwargs):
            resource_manager_result = 'res_hash', ['res_file_1']
            result = resource_manager_result, 'res_file_1', 'package_hash', 42
            return test_client.done_deferred(result)

        c = self.client
        c.resource_server = mock.Mock()

        c.task_server.task_manager.start_task = lambda tid: tid
        c.task_server.task_manager.add_new_task = add_new_task
        c.task_server.task_manager.key_id = 'deadbeef'

        c.resource_server.create_resource_package = mock.Mock(
            side_effect=create_resource_package)
        c.resource_server.add_task = mock.Mock(
            side_effect=add_task)
        c.p2pservice.get_estimated_network_size.return_value = 0

        task = self.client.task_manager.create_task(self.t_dict)
        deferred = rpc.enqueue_new_task(self.client, task)
        task = golem_deferred.sync_wait(deferred)
        task_id = task.header.task_id
        assert isinstance(task, taskbase.Task)
        assert task.header.task_id
        assert c.resource_server.add_task.called

        c.task_server.task_manager.tasks[task_id] = task
        c.task_server.task_manager.tasks_states[task_id] = taskstate.TaskState()
        frames = c.task_server.task_manager.get_output_states(task_id)
        assert frames is not None

    def test_enqueue_new_task_concent_service_disabled(self, *_):
        self.t_dict['concent_enabled'] = True
        self.client.concent_service = mock.Mock()
        self.client.concent_service.enabled = False
        task = self.client.task_manager.create_task(self.t_dict)

        msg = "Cannot create task with concent enabled when " \
              "concent service is disabled"
        with self.assertRaises(Exception, msg=msg):
            golem_deferred.sync_wait(
                rpc.enqueue_new_task(self.client, task)
            )

    def test_create_from_task(self, *_):
        task = self.client.task_manager.create_task(
            copy.deepcopy(TestEnqueueNewTask.T_DICT),
        )
        with self.assertWarnsRegex(
            DeprecationWarning,
            r'instead of dict #2467',
        ):
            self.provider.create_task(task)


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
                    'subtasks': 1,
                }))
