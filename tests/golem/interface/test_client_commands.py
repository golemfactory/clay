import cPickle
import os
import unittest
from collections import namedtuple
from contextlib import contextmanager

from ethereum.utils import denoms
from mock import Mock

from apps.core.benchmark.benchmark import Benchmark
from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder, BlenderRendererOptions, BlenderRenderTask
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from golem.appconfig import AppConfig, MIN_MEMORY_SIZE
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.interface.client.account import account
from golem.interface.client.environments import Environments
from golem.interface.client.network import Network
from golem.interface.client.payments import incomes, payments
from golem.interface.client.resources import Resources
from golem.interface.client.settings import Settings, _virtual_mem, _cpu_count
from golem.interface.client.tasks import Subtasks, Tasks
from golem.interface.command import CommandResult, client_ctx
from golem.interface.exceptions import CommandException
from golem.resource.dirmanager import DirManager
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture


def dbg(result):
    import pprint
    pprint.pprint(result)


class TestAccount(unittest.TestCase):

    def test(self):

        node = Mock()
        node.node_name = 'node1'
        node.key = 'deadbeef'

        client = Mock()
        client.get_node.return_value = node
        client.get_computing_trust.return_value = .01
        client.get_requesting_trust.return_value = .02
        client.get_payment_address.return_value = 'f0f0f0ababab'
        client.get_balance.return_value = 3 * denoms.ether, 2 * denoms.ether, denoms.ether

        with client_ctx(account, client):
            result = account()
            assert result == {
                'node_name': 'node1',
                'provider_reputation': 1,
                'requestor_reputation': 2,
                'Golem_ID': 'deadbeef',
                'finances': {
                    'available_balance': '2.000000 ETH',
                    'deposit_balance': '1.000000 ETH',
                    'eth_address': 'f0f0f0ababab',
                    'local_balance': '3.000000 ETH',
                    'reserved_balance': '1.000000 ETH',
                    'total_balance': '4.000000 ETH'
                },
            }


class TestEnvironments(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        environments = [
            {
                'id': 'env 2',
                'supported': False,
                'active': False,
                'performance': 2000,
                'description': 'description 2'
            },
            {
                'id': 'env 1',
                'supported': True,
                'active': True,
                'performance': 1000,
                'description': 'description 1'
            },
        ]

        client = Mock()
        client.run_benchmark = lambda x: x
        client.get_environments_with_performances.return_value = environments

        cls.client = client

    def test_enable(self):
        with client_ctx(Environments, self.client):
            Environments().enable('Name')
            self.client.change_accept_tasks_for_environment.assert_called_with('Name', True)

    def test_disable(self):
        with client_ctx(Environments, self.client):
            Environments().disable('Name')
            self.client.change_accept_tasks_for_environment.assert_called_with('Name', False)

    def test_show(self):
        with client_ctx(Environments, self.client):
            result_1 = Environments().show(sort=None)

            assert isinstance(result_1, CommandResult)
            assert result_1.type == CommandResult.TABULAR
            assert result_1.data == (
                Environments.table_headers, [
                    ['env 2', 'False', 'False', '2000', 'description 2'],
                    ['env 1', 'True', 'True', '1000', 'description 1'],
                ]
            )

            result_2 = Environments().show(sort='name')

            assert result_2.data
            assert result_1.data != result_2.data

            self.client.get_environments_with_performances.return_value = None

            result_3 = Environments().show(sort=None)
            result_4 = Environments().show(sort='name')

            assert isinstance(result_3, CommandResult)
            assert isinstance(result_4, CommandResult)
            assert result_3.data[0] == Environments.table_headers
            assert result_4.data[0] == Environments.table_headers
            assert not result_3.data[1]
            assert not result_4.data[1]


class TestNetwork(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        PeerInfo = namedtuple('PeerInfo', ['address', 'port', 'key_id', 'node_name'])

        peer_info = [
            PeerInfo(
                '10.0.0.{}'.format(i),
                '2500{}'.format(i),
                'deadbeef0{}'.format(i) * 8,
                'node_{}'.format(i)
            ) for i in range(1, 1 + 6)
        ]

        client = Mock()
        client.get_peer_info.return_value = peer_info

        cls.n_clients = len(peer_info)
        cls.client = client

    def test_status(self):

        with client_ctx(Network, self.client):

            self.client.get_status.return_value = 'Status'
            result = Network().status()

            assert self.client.get_status.called
            assert isinstance(result, basestring)
            assert result
            assert result != 'unknown'

            self.client.get_status.return_value = None
            result = Network().status()

            assert isinstance(result, basestring)
            assert result == 'unknown'

    def test_connect(self):
        with client_ctx(Network, self.client):
            with self.assertRaises(CommandException):
                Network().connect('266.266.0.1', '25000')
                assert not self.client.connect.called

            assert Network().connect('127.0.0.1', '25000') is None
            assert self.client.connect.called

    def test_show(self):
        with client_ctx(Network, self.client):
            net = Network()

            result_1 = net.show(None, full=False)
            result_2 = net.show(None, full=True)

            assert result_1.data[1][0] == [
                '10.0.0.1',
                '25001',
                'deadbeef01deadbe...beef01deadbeef01',
                u'node_1'
            ]

            assert result_2.data[1][0] == [
                '10.0.0.1',
                '25001',
                'deadbeef01' * 8,
                u'node_1'
            ]

            assert isinstance(result_1, CommandResult)
            assert isinstance(result_2, CommandResult)
            assert result_1.type == CommandResult.TABULAR
            assert result_2.type == CommandResult.TABULAR
            assert result_1.data[0] == result_2.data[0]
            assert result_1.data[1] != result_2.data[1]
            assert len(result_1.data[1]) == len(result_1.data[1]) == self.n_clients

            for r1, r2 in zip(result_1.data[1], result_2.data[1]):
                # 'id' (node's key) column
                assert len(r2[2]) > len(r1[2])


class TestPayments(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        incomes_list = [
            {
                'value': float('{}'.format(i)),
                'payer': 'node_{}'.format(i),
                'status': 'PaymentStatus.waiting',
                'block_number': 'deadbeef0{}'.format(i)
            } for i in xrange(1, 6)
        ]

        payments_list = [
            {
                'fee': '{}'.format(i),
                'value': float('0.{}'.format(i)),
                'subtask': 'subtask_{}'.format(i),
                'payee': 'node_{}'.format(i),
                'status': 'PaymentStatus.waiting',
            } for i in xrange(1, 6)
        ]

        client = Mock()
        client.get_incomes_list.return_value = incomes_list
        client.get_payments_list.return_value = payments_list

        cls.n_incomes = len(incomes_list)
        cls.n_payments = len(payments_list)
        cls.client = client

    def test_incomes(self):
        with client_ctx(incomes, self.client):
            result = incomes(None)

            assert isinstance(result, CommandResult)
            assert result.type == CommandResult.TABULAR
            assert len(result.data[1]) == self.n_incomes
            assert result.data[1][0] == [
                u'6e6f64655f31',
                u'waiting',
                u'0.000000 ETH',
                u'deadbeef01'
            ]

    def test_payments(self):
        with client_ctx(payments, self.client):
            result = payments(None)

            assert isinstance(result, CommandResult)
            assert result.type == CommandResult.TABULAR
            assert len(result.data[1]) == self.n_incomes

            assert result.data[1][0][:-1] == [
                u'subtask_1',
                u'6e6f64655f31',
                u'waiting',
                u'0.000000 ETH',
            ]
            assert result.data[1][0][4]


class TestResources(unittest.TestCase):

    def test_show(self):
        dirs = dict(
            example_1='100MB',
            example_2='200MB',
        )

        client = Mock()
        client.get_res_dirs_sizes.return_value = dirs

        with client_ctx(Resources, client):
            assert Resources().show() == dirs

    def test_clear_none(self):
        client = Mock()

        with client_ctx(Resources, client):

            res = Resources()

            with self.assertRaises(CommandException):
                res.clear(False, False)

            assert not client.remove_received_files.called
            assert not client.remove_computed_files.called
            assert not client.remove_distributed_files.called

    def test_clear_provider(self):
        client = Mock()

        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=True, requestor=False)

            assert client.remove_received_files.called
            assert client.remove_computed_files.called
            assert not client.remove_distributed_files.called

    def test_clear_requestor(self):
        client = Mock()

        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=False, requestor=True)

            assert not client.remove_received_files.called
            assert not client.remove_computed_files.called
            assert client.remove_distributed_files.called

    def test_clear_all(self):
        client = Mock()

        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=True, requestor=True)

            assert client.remove_received_files.called
            assert client.remove_computed_files.called
            assert not client.remove_distributed_files.called


def _has_subtask(id):
    return id in ['valid']


class TestTasks(TempDirFixture):

    @classmethod
    def setUpClass(cls):
        super(TestTasks, cls).setUpClass()

        cls.tasks = [
            {
                'id': '745c1d0{}'.format(i),
                'time_remaining': i,
                'subtasks': i + 2,
                'status': 'waiting',
                'progress': i / 100.0
            } for i in xrange(1, 6)
        ]

        cls.subtasks = [
            {
                'node_name': 'node_{}'.format(i),
                'subtask_id': 'subtask_{}'.format(i),
                'time_remaining': 10 - i,
                'status': 'waiting',
                'progress': i / 100.0
            } for i in xrange(1, 6)
        ]

        cls.n_tasks = len(cls.tasks)
        cls.n_subtasks = len(cls.subtasks)
        cls.get_tasks = lambda s, _id: cls.tasks[0] if _id else cls.tasks
        cls.get_subtasks = lambda s, x: cls.subtasks

    def setUp(self):
        super(TestTasks, self).setUp()

        client = Mock()

        client.get_dir_manager.return_value = DirManager(self.path)
        client.get_node_name.return_value = 'test_node'

        client.get_tasks = self.get_tasks
        client.get_subtasks = self.get_subtasks

        self.client = client

    def test_basic_commands(self):
        client = self.client

        with client_ctx(Tasks, client):
            tasks = Tasks()

            assert tasks.restart('valid')
            client.restart_task.assert_called_with('valid')
            assert tasks.abort('valid')
            client.abort_task.assert_called_with('valid')
            assert tasks.delete('valid')
            client.delete_task.assert_called_with('valid')
            assert tasks.resume('valid')
            client.resume_task.assert_called_with('valid')
            assert tasks.stats()
            client.get_task_stats.assert_called_with()

    def test_show(self):
        client = self.client

        with client_ctx(Tasks, client):
            tasks = Tasks()

            one_task = tasks.show('745c1d01', None)
            all_tasks = tasks.show(None, None)

            assert one_task and all_tasks
            assert isinstance(one_task, dict)
            assert isinstance(all_tasks, CommandResult)

            assert one_task == {
                'time_remaining': 1,
                'status': 'waiting',
                'subtasks': 3,
                'id': '745c1d01',
                'progress': '1.00 %'
            }

            assert all_tasks.data[1][0] == [
                '745c1d01', '1', '3', 'waiting', '1.00 %'
            ]

    def test_subtasks(self):
        client = self.client

        with client_ctx(Tasks, client):
            tasks = Tasks()

            subtasks = tasks.subtasks('745c1d01', None)
            assert isinstance(subtasks, CommandResult)
            assert subtasks.data[1][0] == [
                'node_1', 'subtask_1', '9', 'waiting', '1.00 %'
            ]

    @staticmethod
    @contextmanager
    def _run_context(method):
        run = TaskTester.run
        TaskTester.run = method
        yield
        TaskTester.run = run

    def test_load(self):
        client = self.client
        task_file_name = self._create_blender_task(client.get_dir_manager())

        def run_success(instance):
            instance.success_callback()

        def run_error(instance):
            instance.error_callback()

        with client_ctx(Tasks, client):

            with self._run_context(run_success):

                client.enqueue_new_task.call_args = None
                client.enqueue_new_task.called = False

                tasks = Tasks()
                tasks.load(task_file_name, True)

                call_args = client.enqueue_new_task.call_args[0]
                assert len(call_args) == 1
                print call_args[0]
                assert isinstance(call_args[0], BlenderRenderTask)

            with self._run_context(run_error):
                client.enqueue_new_task.call_args = None
                client.enqueue_new_task.called = False

                tasks = Tasks()
                tasks.load(task_file_name, True)

                call_args = client.enqueue_new_task.call_args[0]

                assert len(call_args) == 1
                assert isinstance(call_args[0], BlenderRenderTask)

            with self._run_context(run_error):
                client.enqueue_new_task.call_args = None
                client.enqueue_new_task.called = False

                tasks = Tasks()

                with self.assertRaises(CommandException):
                    tasks.load(task_file_name, False)

    def _create_blender_task(self, dir_manager):

        definition = RenderingTaskDefinition()
        definition.renderer_options = BlenderRendererOptions()

        builder = BlenderRenderTaskBuilder(node_name="ABC", task_definition=definition,
                                           root_path=self.tempdir, dir_manager=dir_manager)

        task = builder.build()
        task.__dict__.update(Benchmark().query_benchmark_task_definition().__dict__)
        task.task_id = "deadbeef"
        task.renderer = "Blender"
        task.docker_images = None
        task.renderer_options = BlenderRendererOptions()

        task_file_name = os.path.join(self.path, 'task_file.gt')

        with open(task_file_name, 'wb') as task_file:
            task_file.write(cPickle.dumps(task))

        return task_file_name


class TestSubtasks(unittest.TestCase):

    def test_show(self):

        client = Mock()

        with client_ctx(Subtasks, client):
            subtasks = Subtasks()

            subtasks.show('valid')
            client.get_subtask.assert_called_with('valid')

            subtasks.show('invalid')
            client.get_subtask.assert_called_with('invalid')

    def test_restart(self):
        client = Mock()

        with client_ctx(Subtasks, client):
            subtasks = Subtasks()

            subtasks.restart('valid')
            client.restart_subtask.assert_called_with('valid')

            subtasks.restart('invalid')
            client.restart_subtask.assert_called_with('invalid')


class TestSettings(TempDirFixture):

    def setUp(self):
        super(TestSettings, self).setUp()

        app_config = AppConfig.load_config(self.tempdir)

        config_desc = ClientConfigDescriptor()
        config_desc.init_from_app_config(app_config)

        client = Mock()
        client.get_config.return_value = config_desc

        self.client = client

    def test_show_all(self):

        with client_ctx(Settings, self.client):
            settings = Settings()

            result = settings.show(False, False, False)
            assert isinstance(result, dict)
            assert len(result) >= len(Settings.settings)

            result = settings.show(True, True, True)
            assert isinstance(result, dict)
            assert len(result) >= len(Settings.settings)

            result = settings.show(True, False, False)
            assert isinstance(result, dict)
            assert len(result) == len(Settings.basic_settings)

            result = settings.show(True, True, False)
            assert isinstance(result, dict)
            assert len(result) >= len(Settings.settings) - len(Settings.requestor_settings)

            result = settings.show(True, False, True)
            assert isinstance(result, dict)
            assert len(result) == len(Settings.basic_settings) + len(Settings.requestor_settings)

    def test_set(self):

        Values = namedtuple('Values', ['valid', 'invalid'])

        bad_common_values = ['a', None, '', [], Exception, lambda x: x]

        _bool = Values([0, 1], bad_common_values)
        _int_gt0 = Values([1], bad_common_values + [0])
        _float_gte0 = Values([1.0, 0.0], bad_common_values)
        _int_m100_100 = Values([-100, 0, 100], bad_common_values)

        _setting_values = {
            'node_name': Values(['node'], ['', None, 12, lambda x: x]),
            'accept_task': _bool,
            'max_resource_size': _int_gt0,
            'use_waiting_for_task_timeout': _bool,
            'waiting_for_task_timeout': _int_gt0,
            'getting_tasks_interval': _int_gt0,
            'getting_peers_interval': _int_gt0,
            'task_session_timeout': _int_gt0,
            'p2p_session_timeout': _int_gt0,
            'requesting_trust': _int_m100_100,
            'computing_trust': _int_m100_100,
            'min_price': _float_gte0,
            'max_price': _float_gte0,
            'use_ipv6': _bool,
            'opt_peer_num': _int_gt0,
            'send_pings': _bool,
            'pings_interval': _int_gt0,
        }

        with client_ctx(Settings, self.client):
            settings = Settings()

            with self.assertRaises(CommandException):
                settings.set('^^^^^^^^^^^', 17)

            for k, values in _setting_values.items():

                valid = values.valid
                invalid = values.invalid

                for vv in valid:
                    settings.set(k, vv)

                for iv in invalid:
                    with self.assertRaises(CommandException):
                        settings.set(k, iv)

            settings.set('max_memory_size', int(_virtual_mem - MIN_MEMORY_SIZE) / 2)
            settings.set('max_memory_size', _virtual_mem - 1)
            settings.set('max_memory_size', MIN_MEMORY_SIZE)

            with self.assertRaises(CommandException):
                settings.set('max_memory_size', MIN_MEMORY_SIZE - 10)
            with self.assertRaises(CommandException):
                settings.set('max_memory_size', _virtual_mem + 10)

            settings.set('num_cores', 1)
            settings.set('num_cores', _cpu_count)

            with self.assertRaises(CommandException):
                settings.set('num_cores', 0)

            with self.assertRaises(CommandException):
                settings.set('num_cores', _cpu_count + 1)
