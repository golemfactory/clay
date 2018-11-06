# pylint: disable=protected-access
from collections import namedtuple
from contextlib import contextmanager
import io
import json
import unittest
from unittest.mock import MagicMock, Mock, mock_open, patch

from ethereum.utils import denoms
import faker
from twisted.internet import defer

from apps.core.task.coretaskstate import TaskDefinition
from golem.appconfig import AppConfig, MIN_MEMORY_SIZE
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.interface.client.account import Account
from golem.interface.client.debug import Debug
from golem.interface.client.environments import Environments
from golem.interface.client.network import Network
from golem.interface.client.payments import incomes, payments
from golem.interface.client.resources import Resources
from golem.interface.client.settings import Settings, _virtual_mem, _cpu_count
from golem.interface.client.tasks import Subtasks, Tasks
from golem.interface.client.terms import Terms
from golem.interface.command import CommandResult, client_ctx
from golem.interface.exceptions import CommandException
from golem.resource.dirmanager import DirManager, DirectoryType
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture


fake = faker.Faker()


def mock_defer(a, b):
    return defer.maybeDeferred(a, b)


class TestAccount(unittest.TestCase):

    def test_show(self):

        node = dict(node_name='node1', key='deadbeef')

        client = Mock()
        client.get_node.return_value = node
        client.get_computing_trust.return_value = .01
        client.get_requesting_trust.return_value = .02
        client.get_payment_address.return_value = 'f0f0f0ababab'
        client.get_balance.return_value = {
            'gnt': 3 * denoms.ether,
            'av_gnt': 2 * denoms.ether,
            'gnt_nonconverted': 0,
            'eth': denoms.ether,
            'gnt_lock': 0.01 * denoms.ether,
            'eth_lock': 0.02 * denoms.ether
        }
        client.get_deposit_balance.return_value = {
            'value': str(1 * denoms.ether),
            'status': 'locked',
            'timelock': '0',
        }

        with client_ctx(Account, client):
            result = Account().info()
            assert result == {
                'node_name': 'node1',
                'provider_reputation': 1,
                'requestor_reputation': 2,
                'Golem_ID': 'deadbeef',
                'finances': {
                    'eth_address': 'f0f0f0ababab',
                    'eth_available': '1 ETH',
                    'eth_locked': '0.02 ETH',
                    'gnt_available': '2 GNT',
                    'gnt_locked': '0.01 GNT',
                    'gnt_unadopted': '0 GNT',
                    'deposit_balance': {
                        'status': 'locked',
                        'value': '1 GNT',
                        'timelock': None,
                    },
                },
            }

    @patch('getpass.getpass')
    def test_unlock_unlocked(self, mock_pass: Mock):
        client = Mock()
        client.is_account_unlocked.return_value = True

        with client_ctx(Account, client):
            result = Account().unlock()
            assert result == "Account already unlocked"
            mock_pass.assert_not_called()

    @patch('twisted.internet.threads.deferToThread', side_effect=mock_defer)
    @patch('getpass.getuser', return_value="John")
    @patch('zxcvbn.zxcvbn', return_value={'score': 2})
    @patch('getpass.getpass', return_value="deadbeef")
    def test_unlock_new(self, mock_pass, mock_zxcvbn, mock_getuser,
                        mock_threads):

        client = Mock()
        client.is_account_unlocked.return_value = False
        client.key_exists.return_value = False

        with client_ctx(Account, client):
            result = Account().unlock()
            assert result == "Account unlock success"
            assert mock_pass.call_count == 2
            mock_getuser.assert_called_once()
            mock_zxcvbn.assert_called_once_with("deadbeef",
                                                user_inputs=["Golem", "John"])
            client.set_password.assert_called_once_with("deadbeef")

    @patch('twisted.internet.threads.deferToThread', side_effect=mock_defer)
    @patch('getpass.getpass', return_value="abc")
    def test_unlock_new_short_error(self, mock_pass, mock_threads):

        client = Mock()
        client.is_account_unlocked.return_value = False
        client.key_exists.return_value = False

        with client_ctx(Account, client):
            result = Account().unlock()
            assert result == "Password is too short, minimum is 5"
            mock_pass.assert_called_once()
            client.set_password.assert_not_called()

    @patch('twisted.internet.threads.deferToThread', side_effect=mock_defer)
    @patch('zxcvbn.zxcvbn', return_value={'score': 1})
    @patch('getpass.getpass', return_value="deadbeef")
    @patch('getpass.getuser', return_value="John")
    def test_unlock_new_strength_error(self, mock_getuser, mock_pass,
                                       mock_zxcvbn, mock_threads):

        client = Mock()
        client.is_account_unlocked.return_value = False
        client.key_exists.return_value = False

        with client_ctx(Account, client):
            result = Account().unlock()
            assert result == "Password is not strong enough. " \
                "Please use capitals, numbers and special characters."
            mock_pass.assert_called_once()
            mock_getuser.assert_called_once()
            mock_zxcvbn.assert_called_once_with("deadbeef",
                                                user_inputs=["Golem", "John"])
            client.set_password.assert_not_called()

    @patch('twisted.internet.threads.deferToThread', side_effect=mock_defer)
    @patch('zxcvbn.zxcvbn', return_value={'score': 1})
    @patch('getpass.getpass', return_value="deadbeef")
    @patch('getpass.getuser', return_value="John")
    def test_unlock_old(self, mock_getuser, mock_pass, mock_zxcvbn,
                        mock_threads):

        client = Mock()
        client.is_account_unlocked.return_value = False
        client.key_exists.return_value = True

        with client_ctx(Account, client):
            result = Account().unlock()
            assert result == "Account unlock success"
            mock_pass.assert_called_once()
            mock_getuser.assert_not_called()
            mock_zxcvbn.assert_not_called()
            client.set_password.assert_called_once_with("deadbeef")


class TestEnvironments(unittest.TestCase):

    def setUp(self):
        super().setUp()

        environments = [
            {
                'id': 'env 2',
                'supported': False,
                'accepted': False,
                'performance': 2000,
                'min_accepted': 17,
                'description': 'description 2'
            },
            {
                'id': 'env 1',
                'supported': True,
                'accepted': True,
                'performance': 1000,
                'min_accepted': 1777,
                'description': 'description 1'
            },
        ]

        client = Mock()
        client.run_benchmark = lambda x: x
        client.get_environments.return_value = environments

        self.client = client

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
                ['env 2', 'False', 'False', '2000', '17', 'description 2'],
                ['env 1', 'True', 'True', '1000', '1777', 'description 1'],
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

    def test_performance_multiplier(self):
        with client_ctx(Environments, self.client):
            Environments().perf_mult()
        self.client._call.assert_called_once_with('performance.multiplier')

    def test_performance_multiplier_set(self):
        anInt = fake.random_int(
            min=MinPerformanceMultiplier.MIN,
            max=MinPerformanceMultiplier.MAX,
        )
        with client_ctx(Environments, self.client):
            Environments().perf_mult_set(multiplier=anInt)
        self.client._call.assert_called_once_with(
            'performance.multiplier.update',
            anInt,
        )


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
        client.get_connected_peers.return_value = peer_info
        client.get_known_peers.return_value = peer_info

        cls.n_clients = len(peer_info)
        cls.client = client

    def tearDown(self):
        self.client.reset_mock()

    def test_status(self):
        with client_ctx(Network, self.client):
            # given
            msg = "Some random message"
            self.client.connection_status.return_value = {
                'msg': msg,
            }

            # when
            result = Network().status()

            # then
            assert self.client.connection_status.called
            assert isinstance(result, str)
            assert result == msg

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

    def test_block_success(self):
        with client_ctx(Network, self.client):
            self.client.block_node.return_value = True, None
            network = Network()
            network.block('node_id')
            self.client.block_node.assert_called_once_with('node_id')

    def test_block_error(self):
        with client_ctx(Network, self.client):
            self.client.block_node.return_value = False, 'error_msg'
            network = Network()
            result = network.block('node_id')
            self.assertEqual(result, 'error_msg')
            self.client.block_node.assert_called_once_with('node_id')

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
            'payer': 'node_{}'.format(i),
            'status': 'waiting',
            'value': '{}'.format(i),
        } for i in range(1, 6)]

        payments_list = [{
            'fee': '{}'.format(i),
            'value': '0.{}'.format(i),
            'subtask': 'subtask_{}'.format(i),
            'payee': 'node_{}'.format(i),
            'status': 'waiting',
        } for i in range(1, 6)]

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
                'node_1', 'waiting', '0.000000 GNT'
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

    def test_show(self):
        dirs = dict(
            sth='100M',
            sample='200M', )

        client = self.client
        client.get_res_dirs_sizes.return_value = dirs

        with client_ctx(Resources, client):
            result = Resources().show()
            assert isinstance(result, CommandResult)
            assert result.type == CommandResult.TABULAR
            assert result.data == (['sth', 'sample'], [['100M', '200M']])

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

            client.clear_dir.assert_called_with(DirectoryType.DISTRIBUTED)

    def test_clear_requestor(self):
        client = self.client
        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=False, requestor=True)

            client.clear_dir.assert_called_with(DirectoryType.RECEIVED)

    def test_clear_all(self):
        client = self.client
        with client_ctx(Resources, client):
            res = Resources()
            res.clear(provider=True, requestor=True)

            assert len(client.clear_dir.mock_calls) == 1


def _has_subtask(id):
    return id in ['valid']


class TestTasks(TempDirFixture):

    @classmethod
    def setUpClass(cls):
        super(TestTasks, cls).setUpClass()

        cls.tasks = [{
            'id': '745c1d0{}'.format(i),
            'time_remaining': i,
            'subtasks_count': i + 2,
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

        cls.reasons = [
            {'avg': '0.8.1', 'reason': 'app_version', 'ntasks': 3},
            {'avg': 7, 'reason': 'max_price', 'ntasks': 2},
            {'avg': None, 'reason': 'environment_missing', 'ntasks': 1},
            {'avg': None,
             'reason': 'environment_not_accepting_tasks', 'ntasks': 1},
            {'avg': None, 'reason': 'requesting_trust', 'ntasks': 0},
            {'avg': None, 'reason': 'deny_list', 'ntasks': 0},
            {'avg': None, 'reason': 'environment_unsupported', 'ntasks': 0}]

        cls.n_tasks = len(cls.tasks)
        cls.n_subtasks = len(cls.subtasks)
        cls.get_tasks = lambda s, _id: dict(cls.tasks[0]) if _id \
            else [dict(t) for t in cls.tasks]
        cls.get_subtasks = lambda s, x: [dict(s) for s in cls.subtasks]
        cls.get_unsupport_reasons = lambda s, x: cls.reasons

    def setUp(self):
        super(TestTasks, self).setUp()

        client = Mock()

        client.get_datadir.return_value = self.path
        client.get_dir_manager.return_value = DirManager(self.path)
        client.get_node_name.return_value = 'test_node'

        client.get_tasks = self.get_tasks
        client.get_subtasks = self.get_subtasks
        client.get_unsupport_reasons = self.get_unsupport_reasons
        client.keys_auth = Mock(public_key=b'a' * 128)

        self.client = client

    def test_basic_commands(self):
        client = self.client

        with client_ctx(Tasks, client):
            tasks = Tasks()

            assert tasks.abort('valid')
            client.abort_task.assert_called_with('valid')
            assert tasks.delete('valid')
            client.delete_task.assert_called_with('valid')
            assert tasks.stats()
            client.get_task_stats.assert_called_with()

    def test_restart_success(self):
        with client_ctx(Tasks, self.client):
            self.client._call.return_value = 'new_task_id', None
            tasks = Tasks()
            result = tasks.restart('task_id')
            self.assertEqual(result, 'new_task_id')
            self.client._call.assert_called_once_with(
                'comp.task.restart',
                'task_id',
                force=False,
            )

    def test_restart_error(self):
        with client_ctx(Tasks, self.client):
            self.client._call.return_value = None, 'error'
            tasks = Tasks()
            with self.assertRaises(CommandException):
                tasks.restart('task_id')
            self.client._call.assert_called_once_with(
                'comp.task.restart',
                'task_id',
                force=False,
            )

    def test_create(self) -> None:
        client = self.client

        definition = TaskDefinition()
        definition.name = "The greatest task ever"
        def_str = json.dumps(definition.to_dict())

        with client_ctx(Tasks, client):
            tasks = Tasks()
            # pylint: disable=no-member
            tasks._Tasks__create_from_json(def_str)  # type: ignore
            # pylint: enable=no-member
            client._call.assert_called_once_with(
                'comp.task.create',
                definition.to_dict(),
            )

            client._call.reset_mock()
            patched_open = "golem.interface.client.tasks.open"
            with patch(patched_open, mock_open(
                read_data='{"name": "Golem task"}'
            )):
                client._call.return_value = ('task_id', None)
                tasks.create("foo")
                task_def = json.loads('{"name": "Golem task"}')
                client._call.assert_called_once_with(
                    'comp.task.create',
                    task_def,
                    force=False,
                )

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
                'time_remaining': '0:00:01',
                'status': 'waiting',
                'subtasks_count': 3,
                'id': '745c1d01',
                'progress': '1.00 %'
            }

            assert all_tasks.data[1][0] == [
                '745c1d01', '0:00:01', '3', 'waiting', '1.00 %'
            ]

            self.client.get_tasks = lambda _: {
                'time_remaining': None,
                'status': 'XXX',
                'substasks': 1,
                'id': 'XXX',
                'progress': 0
            }
            task = tasks.show('XXX', None)
            self.assertDictEqual(task, {
                'time_remaining': '???',
                'status': 'XXX',
                'substasks': 1,
                'id': 'XXX',
                'progress': '0.00 %'
            })

    def test_subtasks_ok(self):
        client = self.client

        with client_ctx(Tasks, client):
            tasks = Tasks()

            subtasks = tasks.subtasks('745c1d01', None)
            assert isinstance(subtasks, CommandResult)
            assert subtasks.data[1][0] == [
                'node_1', 'subtask_1', '0:00:09', 'waiting', '1.00 %'
            ]

    def test_subtasks_error(self):
        with client_ctx(Tasks, self.client):
            self.client.get_subtasks = Mock(return_value=None)
            tasks = Tasks()
            result = tasks.subtasks('task_id', None)
            self.assertEqual(result, 'No subtasks')
            self.client.get_subtasks.assert_called_once_with('task_id')

    def test_unsupport(self):
        client = self.client

        with client_ctx(Tasks, client):
            tasks = Tasks()
            unsupport = tasks.unsupport(0)
            assert isinstance(unsupport, CommandResult)
            assert unsupport.data[1][0] == ['app_version', 3, '0.8.1']
            assert unsupport.data[1][1] == ['max_price', 2, 7]
            assert unsupport.data[1][2] == ['environment_missing', 1, None]

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

    def test_show_ok(self):
        with client_ctx(Subtasks, self.client):
            subtask_dict = {'subtask_id': 'subtask_id'}
            self.client.get_subtask.return_value = subtask_dict, None
            subtasks = Subtasks()
            result = subtasks.show('subtask_id')
            self.assertEqual(result, subtask_dict)
            self.client.get_subtask.assert_called_with('subtask_id')

    def test_show_error(self):
        with client_ctx(Subtasks, self.client):
            self.client.get_subtask.return_value = None, 'error'
            subtasks = Subtasks()
            result = subtasks.show('subtask_id')
            self.assertEqual(result, 'error')
            self.client.get_subtask.assert_called_with('subtask_id')

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
            'accept_tasks': _bool,
            'max_resource_size': _int_gt0,
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


@patch('golem.interface.client.debug.Debug.client')
class TestDebug(unittest.TestCase):
    def setUp(self):
        self.uri = '.'.join(fake.words())
        self.debug = Debug()

    def _rpc(self, *args):
        self.debug.rpc((self.uri,)+args)
        self.debug.client._call.assert_called_once_with(self.uri, *args)

    def test_no_args(self, *_):
        self._rpc()

    def test_one_arg(self, *_):
        self._rpc(fake.uuid4())

    def test_two_args(self, *_):
        self._rpc(fake.uuid4(), fake.pyint())


class TestTerms(unittest.TestCase):

    def setUp(self):
        super(TestTerms, self).setUp()

        self.client = Mock()

    @patch('golem.interface.client.terms.html2text.html2text',
           return_value=object())
    def test_show(self, html2text: MagicMock):
        with client_ctx(Terms, self.client):
            terms = Terms()
            result = terms.show()
            self.client.show_terms.assert_called_once()
            html2text.assert_called_once_with(
                self.client.show_terms.return_value)
            self.assertEqual(result, html2text.return_value)

    @patch('sys.stdin')
    def test_accept(self, stdin):
        stdin.readline.return_value = 'y'
        with client_ctx(Terms, self.client):
            terms = Terms()
            terms.accept()
            self.client.accept_terms.assert_called_once_with(
                enable_monitor=True,
                enable_talkback=True,
            )
