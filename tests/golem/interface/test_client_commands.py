import json
import io
import unittest
import uuid
from collections import namedtuple
from contextlib import contextmanager

from ethereum.utils import denoms
from mock import Mock, mock_open, patch

from apps.core.task.coretaskstate import TaskDefinition
from golem.appconfig import AppConfig, MIN_MEMORY_SIZE
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.interface.client.account import Account
from golem.interface.client.debug import Debug
from golem.interface.client.environments import Environments
from golem.interface.client.network import Network
from golem.interface.client.payments import incomes, payments
from golem.interface.client.resources import Resources
from golem.interface.client.settings import Settings, _virtual_mem, _cpu_count
from golem.interface.client.tasks import Subtasks, Tasks
from golem.interface.command import CommandResult, client_ctx
from golem.interface.exceptions import CommandException
from golem.resource.dirmanager import DirManager, DirectoryType
from golem.rpc.mapping import aliases
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import Client
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture

reference_client = Client(Mock(), CORE_METHOD_MAP)


def assert_client_method(instance, name):
    assert hasattr(reference_client, name)
    return super(Mock, instance).__getattribute__(name)


class TestAccount(unittest.TestCase):
    def test(self):

        node = dict(node_name='node1', key='deadbeef')

        client = Mock()
        client.__getattribute__ = assert_client_method
        client.get_node.return_value = node
        client.get_computing_trust.return_value = .01
        client.get_requesting_trust.return_value = .02
        client.get_payment_address.return_value = 'f0f0f0ababab'
        client.get_balance.return_value = (
            3 * denoms.ether,
            2 * denoms.ether,
            denoms.ether
        )

        with client_ctx(Account, client):
            result = Account().info()
            assert result == {
                'node_name': 'node1',
                'provider_reputation': 1,
                'requestor_reputation': 2,
                'Golem_ID': 'deadbeef',
                'finances': {
                    'available_balance': '2.000000 GNT',
                    'eth_address': 'f0f0f0ababab',
                    'eth_balance': '1.000000 ETH',
                    'reserved_balance': '1.000000 GNT',
                    'total_balance': '3.000000 GNT'
                },
            }


class TestEnvironments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):

        environments = [
            {
                'id': 'env 2',
                'supported': False,
                'accepted': False,
                'performance': 2000,
                'description': 'description 2'
            },
            {
                'id': 'env 1',
                'supported': True,
                'accepted': True,
                'performance': 1000,
                'description': 'description 1'
            },
        ]

        client = Mock()
        client.__getattribute__ = assert_client_method
        client.run_benchmark = lambda x: x
        client.get_environments.return_value = environments

        cls.client = client

    def test_enable(self):
        with client_ctx(Environments, self.client):
            Environments().enable('Name')
            self.client.enable_environment.assert_called_with('Name')

    def test_disable(self):
        with client_ctx(Environments, self.client):
            Environments().disable('Name')
            self.client.disable_environment.assert_called_with('Name')

    def test_show(self):
        with client_ctx(Environments, self.client):
            result_1 = Environments().show(sort=None)

            assert isinstance(result_1, CommandResult)
            assert result_1.type == CommandResult.TABULAR
            assert result_1.data == (Environments.table_headers, [
                ['env 2', 'False', 'False', '2000', 'description 2'],
                ['env 1', 'True', 'True', '1000', 'description 1'],
            ])

            result_2 = Environments().show(sort='name')

            assert result_2.data
            assert result_1.data != result_2.data

            self.client.get_environments.return_value = None

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

        peer_info = [
            dict(
                address='10.0.0.{}'.format(i),
                port='2500{}'.format(i),
                key_id='deadbeef0{}'.format(i) * 8,
                node_name='node_{}'.format(i),
                client_ver='0.0.0') for i in range(1, 1 + 6)
        ]

        client = Mock()
        client.__getattribute__ = assert_client_method
        client.get_connected_peers.return_value = peer_info
        client.get_known_peers.return_value = peer_info

        cls.n_clients = len(peer_info)
        cls.client = client

    def test_status(self):

        with client_ctx(Network, self.client):

            self.client.connection_status.return_value = 'Status'
            result = Network().status()

            assert self.client.connection_status.called
            assert isinstance(result, str)
            assert result
            assert result != 'unknown'

            self.client.connection_status.return_value = None
            result = Network().status()

            assert isinstance(result, str)
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

            self.__assert_peer_result(result_1, result_2)

    def test_dht(self):
        with client_ctx(Network, self.client):
            net = Network()

            result_1 = net.dht(None, full=False)
            result_2 = net.dht(None, full=True)

            self.__assert_peer_result(result_1, result_2)

    def __assert_peer_result(self, result_1, result_2):
        self.assertEqual(result_1.data[1][0], [
            '10.0.0.1',
            '25001',
            'deadbeef01deadbe...beef01deadbeef01',
            'node_1',
            '0.0.0'
        ])

        self.assertEqual(result_2.data[1][0], [
            '10.0.0.1',
            '25001',
            'deadbeef01' * 8,
            'node_1',
            '0.0.0'
        ])

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

        incomes_list = [{
            'value': '{}'.format(i),
            'payer': 'node_{}'.format(i),
            'status': 'waiting',
            'block_number': 'deadbeef0{}'.format(i)
        } for i in range(1, 6)]

        payments_list = [{
            'fee': '{}'.format(i),
            'value': '0.{}'.format(i),
            'subtask': 'subtask_{}'.format(i),
            'payee': 'node_{}'.format(i),
            'status': 'waiting',
        } for i in range(1, 6)]

        client = Mock()
        client.__getattribute__ = assert_client_method
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
                'node_1', 'waiting', '0.000000 GNT', 'deadbeef01'
            ]

    def test_payments(self):
        with client_ctx(payments, self.client):
            result = payments(None)

            assert isinstance(result, CommandResult)
            assert result.type == CommandResult.TABULAR
            assert len(result.data[1]) == self.n_incomes

            assert result.data[1][0][:-1] == [
                'subtask_1',
                'node_1',
                'waiting',
                '0.000000 GNT',
            ]
            assert result.data[1][0][4]


class TestResources(unittest.TestCase):
    def setUp(self):
        super(TestResources, self).setUp()
        self.client = Mock()
        self.client.__getattribute__ = assert_client_method

    def test_show(self):
        dirs = dict(
            example_1='100MB',
            example_2='200MB', )

        client = self.client
        client.get_res_dirs_sizes.return_value = dirs

        with client_ctx(Resources, client):
            assert Resources().show() == dirs

    def test_clear_none(self):
        client = self.client
        with client_ctx(Resources, client):

            res = Resources()

            with self.assertRaises(CommandException):
                res.clear(False, False)

            assert not client.clear_dir.called

    def test_clear_provider(self):
        client = self.client
        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=True, requestor=False)

            assert len(client.clear_dir.mock_calls) == 2

    def test_clear_requestor(self):
        client = self.client
        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=False, requestor=True)

            client.clear_dir.assert_called_with(DirectoryType.DISTRIBUTED)

    def test_clear_all(self):
        client = self.client
        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=True, requestor=True)

            assert len(client.clear_dir.mock_calls) == 2


def _has_subtask(id):
    return id in ['valid']


class TestTasks(TempDirFixture):
    @classmethod
    def setUpClass(cls):
        super(TestTasks, cls).setUpClass()

        cls.tasks = [{
            'id': '745c1d0{}'.format(i),
            'time_remaining': i,
            'subtasks': i + 2,
            'status': 'waiting',
            'progress': i / 100.0
        } for i in range(1, 6)]

        cls.subtasks = [{
            'node_name': 'node_{}'.format(i),
            'subtask_id': 'subtask_{}'.format(i),
            'time_remaining': 10 - i,
            'status': 'waiting',
            'progress': i / 100.0
        } for i in range(1, 6)]

        cls.n_tasks = len(cls.tasks)
        cls.n_subtasks = len(cls.subtasks)
        cls.get_tasks = lambda s, _id: cls.tasks[0] if _id else cls.tasks
        cls.get_subtasks = lambda s, x: cls.subtasks

    def setUp(self):
        super(TestTasks, self).setUp()

        client = Mock()
        client.__getattribute__ = assert_client_method

        client.get_datadir.return_value = self.path
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

    @patch("golem.interface.client.tasks.uuid4")
    def test_create(self, mock_uuid) -> None:
        client = self.client
        mock_uuid.return_value = "new_uuid"

        definition = TaskDefinition()
        definition.task_name = "The greatest task ever!"
        def_str = json.dumps(definition.to_dict())

        with client_ctx(Tasks, client):
            tasks = Tasks()
            tasks.create_from_json(def_str)
            task_def = json.loads(def_str)
            task_def['id'] = "new_uuid"
            client.create_task.assert_called_with(task_def)

            patched_open = "golem.interface.client.tasks.open"
            with patch(patched_open, mock_open(read_data='{}')):
                tasks.create("foo")
                task_def = json.loads('{"id": "new_uuid"}')
                client.create_task.assert_called_with(task_def)

    def test_template(self) -> None:
        tasks = Tasks()

        with patch('sys.stdout', io.StringIO()) as mock_io:
            tasks.template(None)
            output = mock_io.getvalue()

        self.assertIn("bid", output)
        self.assertIn("0.0", output)
        self.assertIn('"subtask_timeout": "0:00:00"', output)

        self.assertEqual(json.loads(output), TaskDefinition().to_dict())

        temp = self.temp_file_name("test_template")
        tasks.template(temp)
        with open(temp) as f:
            content = f.read()
            self.assertEqual(content, output)

        with client_ctx(Tasks, self.client):
            Tasks.client.get_task.return_value = TaskDefinition().to_dict()
            tasks.dump('id', temp)

        with open(temp) as f:
            content_dump = f.read()
            self.assertEqual(content, content_dump)

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


class TestSubtasks(unittest.TestCase):
    def setUp(self):
        super(TestSubtasks, self).setUp()

        self.client = Mock()
        self.client.__getattribute__ = assert_client_method

    def test_show(self):
        client = self.client

        with client_ctx(Subtasks, client):
            subtasks = Subtasks()

            subtasks.show('valid')
            client.get_subtask.assert_called_with('valid')

            subtasks.show('invalid')
            client.get_subtask.assert_called_with('invalid')

    def test_restart(self):
        client = self.client

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
        client.__getattribute__ = assert_client_method
        client.get_settings.return_value = config_desc.__dict__

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
            assert len(result) >= len(Settings.settings) - len(
                Settings.requestor_settings)

            result = settings.show(True, False, True)
            assert isinstance(result, dict)
            assert len(result) == len(Settings.basic_settings) + len(
                Settings.requestor_settings)

    def test_set(self):

        Values = namedtuple('Values', ['valid', 'invalid'])

        bad_common_values = ['a', None, '', [], Exception, lambda x: x]

        _bool = Values([0, 1], bad_common_values)
        _int_gt0 = Values([1], bad_common_values + [0])
        _float_gte0 = Values([1.0, 0.0], bad_common_values)
        _float_m1_1 = Values([-1.0, 1.0], bad_common_values)

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
            'requesting_trust': _float_m1_1,
            'computing_trust': _float_m1_1,
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

            for k, values in list(_setting_values.items()):

                valid = values.valid
                invalid = values.invalid

                for vv in valid:
                    settings.set(k, vv)

                for iv in invalid:
                    with self.assertRaises(CommandException):
                        settings.set(k, iv)

            settings.set(
                'max_memory_size',
                MIN_MEMORY_SIZE + int(_virtual_mem - MIN_MEMORY_SIZE) / 2)
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


class TestDebug(unittest.TestCase):
    def setUp(self):
        super(TestDebug, self).setUp()

        self.client = Mock()
        self.client.__getattribute__ = assert_client_method

    def test_show(self):
        client = self.client

        with client_ctx(Debug, client):
            debug = Debug()
            task_id = str(uuid.uuid4())

            debug.rpc((aliases.Network.ident, ))
            assert client.get_node.called

            debug.rpc((aliases.Task.task, task_id))
            client.get_task.assert_called_with(task_id)

            debug.rpc((aliases.Task.subtasks_borders, task_id, 2))
            client.get_subtasks_borders.assert_called_with(task_id, 2)

            with self.assertRaises(CommandException):
                debug.rpc((task_id, ))
