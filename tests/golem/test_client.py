# pylint: disable=protected-access,too-many-lines
import datetime
import json
import os
import time
import uuid
from random import Random
from types import MethodType
from unittest import mock
from unittest import TestCase
from unittest.mock import (
    MagicMock,
    Mock,
    patch,
)

from ethereum.utils import denoms
from freezegun import freeze_time
from pydispatch import dispatcher
from twisted.internet.defer import Deferred

from apps.dummy.task.dummytask import DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefinition
import golem
from golem import model
from golem import testutils
from golem.client import Client, ClientTaskComputerEventListener, \
    DoWorkService, MonitoringPublisherService, \
    NetworkConnectionPublisherService, \
    ResourceCleanerService, TaskArchiverService, \
    TaskCleanerService
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_string
from golem.core.deferred import sync_wait
from golem.core.simpleserializer import DictSerializer
from golem.environments.environment import Environment as DefaultEnvironment
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import PeerSessionInfo
from golem.report import StatusPublisher
from golem.resource.dirmanager import DirManager
from golem.rpc.mapping.rpceventnames import UI, Environment
from golem.task.acl import Acl
from golem.task.taskbase import Task
from golem.task.taskserver import TaskServer
from golem.task.taskstate import TaskState, TaskStatus, SubtaskStatus, \
    TaskTestStatus
from golem.task.tasktester import TaskTester
from golem.tools import testwithreactor
from golem.tools.assertlogs import LogTestCase

from .ethereum.test_fundslocker import make_mock_task as \
    make_fundslocker_mock_task

random = Random(__name__)


def mock_async_run(req, success, error):
    deferred = Deferred()
    if success:
        deferred.addCallback(success)
    if error:
        deferred.addErrback(error)

    try:
        result = req.method(*req.args, **req.kwargs)
    except Exception as e:  # pylint: disable=broad-except
        deferred.errback(e)
    else:
        deferred.callback(result)

    return deferred


def random_hex_str() -> str:
    return str(uuid.uuid4()).replace('-', '')


def done_deferred(return_value=None):
    deferred = Deferred()
    deferred.callback(return_value)
    return deferred


def make_mock_ets(eth=100, gnt=100):
    ets = MagicMock(name="MockTransactionSystem")
    ets.get_balance.return_value = (
        gnt * denoms.ether,
        gnt * denoms.ether,
        eth * denoms.ether,
        time.time(),
        time.time(),
    )
    ets.eth_for_batch_payment.return_value = 0.0001 * denoms.ether
    ets.eth_base_for_batch_payment.return_value = 0.001 * denoms.ether
    ets.get_payment_address.return_value = '0x' + 40 * 'a'
    return ets


@patch('golem.client.node_info_str')
@patch(
    'golem.network.concent.handlers_library.HandlersLibrary'
    '.register_handler',
)
@patch('signal.signal')
@patch('golem.network.p2p.node.Node.collect_network_info')
def make_client(*_, **kwargs):
    default_kwargs = {
        'app_config': Mock(),
        'config_desc': ClientConfigDescriptor(),
        'keys_auth': Mock(
            _private_key='a' * 32,
            key_id='a' * 64,
            public_key=b'a' * 128,
        ),
        'database': Mock(),
        'transaction_system': Mock(),
        'connect_to_known_hosts': False,
        'use_docker_manager': False,
        'use_monitor': False,
    }
    default_kwargs.update(kwargs)
    client = Client(**default_kwargs)
    return client


class TestClientBase(testwithreactor.TestDatabaseWithReactor):
    def setUp(self):
        super().setUp()
        self.client = make_client(datadir=self.path)

    def tearDown(self):
        self.client.quit()
        super().tearDown()


@patch(
    'golem.network.concent.handlers_library.HandlersLibrary'
    '.register_handler',
)
class TestClient(TestClientBase):
    # FIXME: if we someday decide to run parallel tests,
    # this may completely break. Issue #2456
    # pylint: disable=attribute-defined-outside-init

    def test_get_payments(self, *_):
        ets = self.client.transaction_system
        assert self.client.get_payments_list() == \
            ets.get_payments_list.return_value

    def test_get_incomes(self, *_):
        ets = self.client.transaction_system
        ets.get_incomes_list.return_value = []
        self.client.get_incomes_list()
        ets.get_incomes_list.assert_called_once_with()

    def test_withdraw(self, *_):
        ets = self.client.transaction_system
        ets.return_value = ets
        ets.return_value.eth_base_for_batch_payment.return_value = 0
        self.client.withdraw('123', '0xdead', 'ETH')
        ets.withdraw.assert_called_once_with(123, '0xdead', 'ETH')

    def test_get_withdraw_gas_cost(self, *_):
        dest = '0x' + 40 * '0'
        ets = Mock()
        ets = self.client.transaction_system
        self.client.get_withdraw_gas_cost('123', dest, 'ETH')
        ets.get_withdraw_gas_cost.assert_called_once_with(123, dest, 'ETH')

    def test_payment_address(self, *_):
        payment_address = self.client.get_payment_address()
        self.assertIsInstance(payment_address, str)
        self.assertTrue(len(payment_address) > 0)

    def test_remove_resources(self, *_):
        def unique_dir():
            d = os.path.join(self.path, str(uuid.uuid4()))
            if not os.path.exists(d):
                os.makedirs(d)
            return d

        c = self.client
        c.task_server = Mock()
        c.task_server.get_task_computer_root.return_value = unique_dir()
        c.task_server.task_manager.get_task_manager_root.return_value = \
            unique_dir()

        c.resource_server = Mock()
        c.resource_server.get_distributed_resource_root.return_value = \
            unique_dir()

        d = c.get_distributed_files_dir()
        self.assertIn(self.path, os.path.normpath(d))  # normpath for mingw
        self.additional_dir_content([3], d)
        c.remove_distributed_files()
        self.assertEqual(os.listdir(d), [])

        d = c.get_received_files_dir()
        self.assertIn(self.path, d)
        self.additional_dir_content([3], d)
        c.remove_received_files()
        self.assertEqual(os.listdir(d), [])

    def test_datadir_lock(self, *_):
        # Let's use non existing dir as datadir here to check how the Client
        # is able to cope with that.
        datadir = os.path.join(self.path, "non-existing-dir")
        self.client = make_client(datadir=datadir)
        self.assertEqual(self.client.config_desc.node_address, '')
        with self.assertRaises(IOError):
            make_client(datadir=datadir)

    def test_quit(self, *_):
        self.client.db = None
        self.client.quit()

    def test_collect_gossip(self, *_):
        self.client.start_network()
        self.client.collect_gossip()

    def test_activate_hw_preset(self, *_):
        config = self.client.config_desc
        config.hardware_preset_name = 'non-existing'
        config.num_cores = 0
        config.max_memory_size = 0
        config.max_resource_size = 0

        self.client.activate_hw_preset('custom')

        assert config.hardware_preset_name == 'custom'
        assert config.num_cores > 0
        assert config.max_memory_size > 0
        assert config.max_resource_size > 0

    def test_presets(self, *_):  # noqa This test depends on DatabaseFixture pylint: disable=no-self-use
        Client.save_task_preset("Preset1", "TaskType1", "data1")
        Client.save_task_preset("Preset2", "TaskType1", "data2")
        Client.save_task_preset("Preset1", "TaskType2", "data3")
        Client.save_task_preset("Preset3", "TaskType2", "data4")
        presets = Client.get_task_presets("TaskType1")
        assert len(presets) == 2
        assert presets["Preset1"] == "data1"
        assert presets["Preset2"] == "data2"
        presets = Client.get_task_presets("TaskType2")
        assert len(presets) == 2
        assert presets["Preset1"] == "data3"
        assert presets["Preset3"] == "data4"
        Client.delete_task_preset("TaskType2", "Preset1")
        presets = Client.get_task_presets("TaskType1")
        assert len(presets) == 2
        assert presets["Preset1"] == "data1"
        presets = Client.get_task_presets("TaskType2")
        assert len(presets) == 1
        assert presets.get("Preset1") is None

    @patch('golem.environments.environmentsmanager.'
           'EnvironmentsManager.load_config')
    @patch('golem.client.SystemMonitor')
    @patch('golem.client.P2PService.connect_to_network')
    def test_start_stop(self, connect_to_network, *_):
        deferred = Deferred()
        connect_to_network.side_effect = lambda *_: deferred.callback(True)
        self.client.are_terms_accepted = lambda: True

        self.client.start()
        sync_wait(deferred)

        self.client.p2pservice.disconnect = Mock(
            side_effect=self.client.p2pservice.disconnect)
        self.client.task_server.disconnect = Mock(
            side_effect=self.client.task_server.disconnect)

        self.client.stop()

        self.client.p2pservice.disconnect.assert_called_once()
        self.client.task_server.disconnect.assert_called_once()

    @patch('golem.environments.environmentsmanager.'
           'EnvironmentsManager.load_config')
    @patch('golem.client.SystemMonitor')
    @patch('golem.client.P2PService.connect_to_network')
    def test_pause_resume(self, *_):
        self.client.start()

        assert self.client.p2pservice.active
        assert self.client.task_server.active

        self.client.pause()

        assert not self.client.p2pservice.active
        assert not self.client.task_server.active

        self.client.resume()

        assert self.client.p2pservice.active
        assert self.client.task_server.active

        self.client.stop()

    @patch('golem.client.path')
    @patch('golem.client.async_run', mock_async_run)
    @patch('golem.network.concent.client.ConcentClientService.start')
    @patch('golem.client.SystemMonitor')
    @patch('golem.client.P2PService.connect_to_network')
    def test_restart_task(self, connect_to_network, *_):
        self.client.apps_manager.load_all_apps()

        deferred = Deferred()
        connect_to_network.side_effect = lambda *_: deferred.callback(True)
        self.client.are_terms_accepted = lambda: True
        self.client.start()
        sync_wait(deferred)

        def create_resource_package(*_args):
            result = 'package_path', 'package_sha1'
            return done_deferred(result)

        def add_task(*_args, **_kwargs):
            resource_manager_result = 'res_hash', ['res_file_1']
            result = resource_manager_result, 'res_file_1', 'package_hash', 0
            return done_deferred(result)

        self.client.resource_server = Mock(
            create_resource_package=Mock(side_effect=create_resource_package),
            add_task=Mock(side_effect=add_task)
        )

        task_manager = self.client.task_server.task_manager

        task_manager.dump_task = Mock()
        task_manager.listen_address = '127.0.0.1'
        task_manager.listen_port = 40103

        some_file_path = self.new_path / "foo"
        # pylint thinks it's PurePath, but it's a concrete path
        some_file_path.touch()  # pylint: disable=no-member

        task_dict = {
            'bid': 5.0,
            'name': 'test task',
            'options': {
                'difficulty': 1337,
                'output_path': '',
            },
            'resources': [str(some_file_path)],
            'subtask_timeout': timeout_to_string(3),
            'subtasks': 1,
            'timeout': timeout_to_string(3),
            'type': 'Dummy',
        }

        task_id, error = self.client.create_task(task_dict)

        assert task_id
        assert not error

        new_task_id, error = self.client.restart_task(task_id)
        assert new_task_id
        assert not error
        assert len(task_manager.tasks_states) == 2

        assert task_id != new_task_id
        assert task_manager.tasks_states[
            task_id].status == TaskStatus.restarted
        assert all(
            ss.subtask_status == SubtaskStatus.restarted
            for ss
            in task_manager.tasks_states[task_id].subtask_states.values())
        assert task_manager.tasks_states[new_task_id].status \
            == TaskStatus.waiting

    @patch('golem.client.get_timestamp_utc')
    def test_clean_old_tasks_no_tasks(self, *_):
        self.client.get_tasks = Mock(return_value=[])
        self.client.delete_task = Mock()
        self.client.clean_old_tasks()
        self.client.delete_task.assert_not_called()

    @patch('golem.client.get_timestamp_utc')
    def test_clean_old_tasks_only_new(self, get_timestamp, *_):
        self.client.config_desc.clean_tasks_older_than_seconds = 5
        self.client.get_tasks = Mock(return_value=[{
            'time_started': 0,
            'timeout': timeout_to_string(5),
            'id': 'new_task'
        }])
        get_timestamp.return_value = 7
        self.client.delete_task = Mock()
        self.client.clean_old_tasks()
        self.client.delete_task.assert_not_called()

    @patch('golem.client.get_timestamp_utc')
    def test_clean_old_tasks_old_and_new(self, get_timestamp, *_):
        self.client.config_desc.clean_tasks_older_than_seconds = 5
        self.client.get_tasks = Mock(return_value=[{
            'time_started': 0,
            'timeout': timeout_to_string(5),
            'id': 'old_task'
        }, {
            'time_started': 5,
            'timeout': timeout_to_string(5),
            'id': 'new_task'
        }])
        get_timestamp.return_value = 10
        self.client.delete_task = Mock()
        self.client.clean_old_tasks()
        self.client.delete_task.assert_called_once_with('old_task')

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

            with patch.object(self.client,
                              'p2pservice',
                              spec=P2PService) as p2p, \
                    patch.object(self.client, 'task_server', spec=TaskServer), \
                    patch('golem.client.Mask') as mask:

                p2p.get_estimated_network_size.return_value = network_size
                p2p.get_performance_percentile_rank.return_value = perf_rank

                task = MagicMock()
                task.get_total_tasks.return_value = num_tasks

                self.client._get_mask_for_task(task)

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


class TestClientRestartSubtasks(TestClientBase):
    def setUp(self):
        super().setUp()
        self.ts = self.client.transaction_system
        self.client.funds_locker.persist = False

        self.task = make_fundslocker_mock_task()
        self.client.funds_locker.lock_funds(self.task)

        self.client.task_server = Mock()

    def test_restart_by_frame(self):
        # given
        frame_subtasks = {
            'subtask_id1': Mock(),
            'subtask_id2': Mock(),
        }
        self.client.task_server.task_manager.get_frame_subtasks.return_value = \
            frame_subtasks

        frame = 10

        # when
        self.client.restart_frame_subtasks(self.task.header.task_id, frame)

        # then
        self.client.task_server.task_manager.restart_frame_subtasks.\
            assert_called_with(self.task.header.task_id, frame)
        self.ts.lock_funds_for_payments.assert_called_with(
            self.task.subtask_price, len(frame_subtasks))

    def test_restart_subtask(self):
        # given
        self.client.task_server.task_manager.get_task_id.return_value = \
            self.task.header.task_id

        # when
        self.client.restart_subtask('subtask_id')

        # then
        self.client.task_server.task_manager.restart_subtask.\
            assert_called_with('subtask_id')
        self.ts.lock_funds_for_payments.assert_called_with(
            self.task.subtask_price, 1)


class TestDoWorkService(testwithreactor.TestWithReactor):
    def setUp(self):
        super().setUp()

        client = Mock()
        client.p2pservice = Mock()
        client.p2pservice.peers = {str(uuid.uuid4()): Mock()}
        client.task_server = Mock()
        client.resource_server = Mock()
        client.ranking = Mock()
        client.config_desc.send_pings = False
        self.client = client
        self.do_work_service = DoWorkService(client)

    @patch('golem.client.logger')
    def test_run(self, logger):
        self.do_work_service._run()

        self.client.p2pservice.ping_peers.assert_not_called()
        logger.exception.assert_not_called()
        self.client.p2pservice.sync_network.assert_called()
        self.client.resource_server.sync_network.assert_called()
        self.client.ranking.sync_network.assert_called()

    @patch('golem.client.logger')
    def test_pings(self, logger):
        self.client.config_desc.send_pings = True

        # Make methods throw exceptions
        def raise_exc():
            raise Exception('Test exception')

        self.client.p2pservice.sync_network = raise_exc
        self.client.task_server.sync_network = raise_exc
        self.client.resource_server.sync_network = raise_exc
        self.client.ranking.sync_network = raise_exc

        self.do_work_service._run()

        self.client.p2pservice.ping_peers.assert_called()
        assert logger.exception.call_count == 4

    @freeze_time("2018-01-01 00:00:00")
    def test_time_for(self):
        key = 'payments'
        interval = 4.0

        assert key not in self.do_work_service._check_ts
        assert self.do_work_service._time_for(key, interval)
        assert key in self.do_work_service._check_ts

        next_check = self.do_work_service._check_ts[key]

        with freeze_time("2018-01-01 00:00:01"):
            assert not self.do_work_service._time_for(key, interval)
            assert self.do_work_service._check_ts[key] == next_check

        with freeze_time("2018-01-01 00:01:00"):
            assert self.do_work_service._time_for(key, interval)
            assert self.do_work_service._check_ts[key] == time.time() + interval

    @freeze_time("2018-01-01 00:00:00")
    def test_intervals(self):
        self.do_work_service._run()

        assert self.client.p2pservice.sync_network.called
        assert self.client.task_server.sync_network.called
        assert self.client.resource_server.sync_network.called
        assert self.client.ranking.sync_network.called

        self.client.reset_mock()

        with freeze_time("2018-01-01 00:00:02"):
            self.do_work_service._run()

            assert self.client.p2pservice.sync_network.called
            assert self.client.task_server.sync_network.called
            assert self.client.resource_server.sync_network.called
            assert self.client.ranking.sync_network.called

        with freeze_time("2018-01-01 00:01:00"):
            self.do_work_service._run()

            assert self.client.p2pservice.sync_network.called
            assert self.client.task_server.sync_network.called
            assert self.client.resource_server.sync_network.called
            assert self.client.ranking.sync_network.called


class TestMonitoringPublisherService(testwithreactor.TestWithReactor):
    def setUp(self):
        task_server = Mock()
        task_server.task_keeper = Mock()
        task_server.task_keeper.get_all_tasks.return_value = list()
        task_server.task_keeper.supported_tasks = list()
        task_server.task_computer.stats = dict()
        self.service = MonitoringPublisherService(
            task_server,
            interval_seconds=1,
        )

    @patch('golem.client.logger')
    @patch('golem.client.dispatcher.send')
    def test_run(self, send, logger):
        self.service._run()

        logger.debug.assert_not_called()
        assert send.call_count == 3


class TestNetworkConnectionPublisherService(testwithreactor.TestWithReactor):
    def setUp(self):
        self.client = Mock()
        self.service = NetworkConnectionPublisherService(
            self.client,
            interval_seconds=1,
        )

    @patch('golem.client.logger')
    def test_run(self, logger):
        self.service._run()

        logger.debug.assert_not_called()
        self.client._publish.assert_called()


class TestTaskArchiverService(testwithreactor.TestWithReactor):
    def setUp(self):
        self.task_archiver = Mock()
        self.service = TaskArchiverService(self.task_archiver)

    @patch('golem.client.logger')
    def test_run(self, logger):
        self.service._run()

        logger.debug.assert_not_called()
        self.task_archiver.do_maintenance.assert_called()


class TestResourceCleanerService(testwithreactor.TestWithReactor):
    def setUp(self):
        self.older_than_seconds = 5
        self.client = Mock()
        self.service = ResourceCleanerService(
            self.client,
            interval_seconds=1,
            older_than_seconds=self.older_than_seconds,
        )

    def test_run(self):
        self.service._run()

        self.client.remove_distributed_files.assert_called_with(
            self.older_than_seconds,
        )
        self.client.remove_received_files.assert_called_with(
            self.older_than_seconds,
        )


class TestTaskCleanerService(testwithreactor.TestWithReactor):
    def setUp(self):
        self.client = Mock(spec=Client)
        self.service = TaskCleanerService(
            client=self.client,
            interval_seconds=1
        )

    def test_run(self):
        self.service._run()
        self.client.clean_old_tasks.assert_called_once()


@patch('signal.signal')  # pylint: disable=too-many-ancestors
@patch('golem.network.p2p.node.Node.collect_network_info')
class TestClientRPCMethods(TestClientBase, LogTestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.client.apps_manager.load_all_apps()
        self.client.sync = Mock()
        self.client.p2pservice = Mock(peers={})
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler', ):
            self.client.task_server = TaskServer(
                node=Node(),
                config_desc=ClientConfigDescriptor(),
                client=self.client,
                use_docker_manager=False,
                apps_manager=self.client.apps_manager,
            )
        self.client.monitor = Mock()

    def test_node(self, *_):
        c = self.client

        self.assertIsInstance(c.get_node(), dict)

        self.assertIsInstance(c.get_node_key(), str)
        self.assertIsNotNone(c.get_node_key())

        c.node.key = None

        self.assertNotIsInstance(c.get_node_key(), str)
        self.assertIsNone(c.get_node_key())

        self.assertIsInstance(c.get_public_key(), bytes)
        self.assertEqual(c.get_public_key(), c.keys_auth.public_key)

    def test_directories(self, *_):
        c = self.client

        def unique_dir():
            d = self.new_path / str(uuid.uuid4())
            d.mkdir(exist_ok=True)
            return d

        c.resource_server = Mock()
        c.resource_server.get_distributed_resource_root.return_value = \
            unique_dir()

        self.assertIsInstance(c.get_datadir(), str)
        self.assertIsInstance(c.get_dir_manager(), DirManager)

        res_dirs = c.get_res_dirs()

        self.assertIsInstance(res_dirs, dict)
        self.assertTrue(len(res_dirs) == 2)

        for key, value in list(res_dirs.items()):
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)
            self.assertTrue(self.path in value)

        res_dir_sizes = c.get_res_dirs_sizes()

        for key, value in list(res_dir_sizes.items()):
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)
            self.assertTrue(key in res_dirs)

    def test_get_estimated_cost(self, *_):
        self.client.transaction_system = make_mock_ets()
        self.assertEqual(
            self.client.get_estimated_cost(
                "task type",
                {
                    "price": 150,
                    "subtask_time": 2.5,
                    "num_subtasks": 5,
                },
            ),
            {
                "GNT": 1875.0,
                "ETH": 0.0001,
            },
        )

    @patch('golem.client.get_resources_for_task')
    def test_enqueue_new_task_from_type(self, *_):
        c = self.client
        c.concent_service = Mock()
        c.funds_locker.persist = False
        c.resource_server = Mock()
        c.task_server = Mock()
        c.p2pservice.get_estimated_network_size.return_value = 0

        task_fixed_header = Mock(
            concent_enabled=False,
        )
        task_header = Mock(
            max_price=1 * 10**18,
            task_id=str(uuid.uuid4()),
            subtask_timeout=37,
            fixed_header=task_fixed_header,
        )
        task = Mock(
            header=task_header,
            get_resources=Mock(return_value=[]),
            total_tasks=5,
            get_price=Mock(return_value=900),
            subtask_price=1000,
        )

        c.concent_service.enabled = False
        c.enqueue_new_task(task)
        assert not c.task_server.task_manager.create_task.called
        task_mock = MagicMock()
        task_mock.header.max_price = 1 * 10**18
        task_mock.header.subtask_timeout = 158
        task_mock.total_tasks = 3
        price = task_mock.header.max_price * task_mock.total_tasks
        task_mock.get_price.return_value = price
        task_mock.subtask_price = 1000
        c.task_server.task_manager.create_task.return_value = task_mock
        c.concent_service.enabled = True
        c.enqueue_new_task(dict(
            max_price=1 * 10**18,
            task_id=str(uuid.uuid4())
        ))
        c.funds_locker.persist = True
        assert c.task_server.task_manager.create_task.called
        c.transaction_system.concent_deposit.assert_called_once_with(
            required=mock.ANY,
            expected=mock.ANY,
        )
        c.funds_locker.persist = False

    @patch('golem.client.path')
    @patch('golem.client.async_run', side_effect=mock_async_run)
    def test_enqueue_new_task(self, *_):
        t_dict = {
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

        def start_task(_, tid):
            return tid

        def add_new_task(instance, task, *_args, **_kwargs):
            instance.tasks_states[task.header.task_id] = TaskState()

        def create_resource_package(*_args):
            result = 'package_path', 'package_sha1'
            return done_deferred(result)

        def add_task(*_args, **_kwargs):
            resource_manager_result = 'res_hash', ['res_file_1']
            result = resource_manager_result, 'res_file_1', 'package_hash', 42
            return done_deferred(result)

        c = self.client
        c.resource_server = Mock()

        c.task_server.task_manager.start_task = MethodType(
            start_task, c.task_server.task_manager)
        c.task_server.task_manager.add_new_task = MethodType(
            add_new_task, c.task_server.task_manager)
        c.task_server.task_manager.key_id = 'deadbeef'

        c.resource_server.create_resource_package = Mock(
            side_effect=create_resource_package)
        c.resource_server.add_task = Mock(
            side_effect=add_task)
        c.p2pservice.get_estimated_network_size.return_value = 0

        deferred, task_id = c.enqueue_new_task(t_dict)
        task = sync_wait(deferred)
        assert isinstance(task, Task)
        assert task.header.task_id
        assert task.header.task_id == task_id
        assert c.resource_server.add_task.called

        c.task_server.task_manager.tasks[task_id] = task
        c.task_server.task_manager.tasks_states[task_id] = TaskState()
        frames = c.get_subtasks_frames(task_id)
        assert frames is not None

    def test_enqueue_new_task_concent_service_disabled(self, *_):
        c = self.client

        t_dict = {
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
            },
            'concent_enabled': True,
        }

        c.concent_service = Mock()
        c.concent_service.enabled = False

        msg = "Cannot create task with concent enabled when " \
              "concent service is disabled"
        with self.assertRaises(Exception, msg=msg):
            c.enqueue_new_task(t_dict)

    def test_get_balance(self, *_):
        c = self.client

        c.transaction_system = Mock()

        result = {
            'gnt_available': 2,
            'gnt_locked': 1,
            'gnt_nonconverted': 0,
            'gnt_update_time': None,
            'eth_available': 2,
            'eth_locked': 1,
            'eth_update_time': None,
            'block_number': 222,
        }
        c.transaction_system.get_balance.return_value = result
        balance = sync_wait(c.get_balance())
        assert balance == {
            'gnt': "2",
            'av_gnt': "2",
            'eth': "2",
            'gnt_nonconverted': "0",
            'gnt_lock': "1",
            'eth_lock': "1",
            'last_gnt_update': "None",
            'last_eth_update': "None",
            'block_number': "222",
        }
        assert all(isinstance(entry, str) for entry in balance)

    def test_run_benchmark(self, *_):
        from apps.blender.blenderenvironment import BlenderEnvironment
        from apps.blender.benchmark.benchmark import BlenderBenchmark
        from apps.lux.luxenvironment import LuxRenderEnvironment
        from apps.lux.benchmark.benchmark import LuxBenchmark

        benchmark_manager = self.client.task_server.benchmark_manager
        benchmark_manager.run_benchmark = Mock()
        benchmark_manager.run_benchmark.side_effect = lambda b, tb, e, c, ec: \
            c(True)

        with self.assertRaisesRegex(Exception, "Unknown environment"):
            sync_wait(self.client.run_benchmark(str(uuid.uuid4())))

        sync_wait(self.client.run_benchmark(BlenderEnvironment.get_id()))

        assert benchmark_manager.run_benchmark.call_count == 1
        assert isinstance(benchmark_manager.run_benchmark.call_args[0][0],
                          BlenderBenchmark)

        sync_wait(self.client.run_benchmark(LuxRenderEnvironment.get_id()))

        assert benchmark_manager.run_benchmark.call_count == 2
        assert isinstance(benchmark_manager.run_benchmark.call_args[0][0],
                          LuxBenchmark)

        result = sync_wait(self.client.run_benchmark(
            DefaultEnvironment.get_id()))
        assert result > 100.0
        assert benchmark_manager.run_benchmark.call_count == 2

    def test_run_benchmark_fail(self, *_):
        from apps.dummy.dummyenvironment import DummyTaskEnvironment

        def raise_exc(*_args, **_kwargs):
            raise Exception('Test exception')

        with patch("golem.docker.image.DockerImage.is_available",
                   return_value=True), \
                patch("golem.docker.job.DockerJob.__init__",
                      side_effect=raise_exc), \
                self.assertRaisesRegex(Exception, 'Test exception'):
            sync_wait(self.client.run_benchmark(DummyTaskEnvironment.get_id()))

    def test_config_changed(self, *_):
        c = self.client

        c._publish = Mock()
        c.lock_config(True)
        c._publish.assert_called_with(UI.evt_lock_config, True)

        c._publish = Mock()
        c.config_changed()
        c._publish.assert_called_with(Environment.evt_opts_changed)

    def test_settings(self, *_):
        c = self.client

        new_node_name = str(uuid.uuid4())
        self.assertNotEqual(c.get_setting('node_name'), new_node_name)

        c.update_setting('node_name', new_node_name)
        self.assertEqual(c.get_setting('node_name'), new_node_name)
        self.assertEqual(c.get_settings()['node_name'], new_node_name)

        newer_node_name = str(uuid.uuid4())
        self.assertNotEqual(c.get_setting('node_name'), newer_node_name)

        settings = c.get_settings()
        self.assertIsInstance(settings['min_price'], str)
        self.assertIsInstance(settings['max_price'], str)

        settings['node_name'] = newer_node_name
        c.update_settings(settings)
        self.assertEqual(c.get_setting('node_name'), newer_node_name)

        # invalid settings
        with self.assertRaises(KeyError):
            c.get_setting(str(uuid.uuid4()))

        with self.assertRaises(KeyError):
            c.update_setting(str(uuid.uuid4()), 'value')

    def test_publisher(self, *_):
        from golem.rpc.session import Publisher

        c = self.client
        self.assertIsNone(c.rpc_publisher)

        rpc_session = Mock()
        publisher = Publisher(rpc_session)

        c.set_rpc_publisher(publisher)
        self.assertIsInstance(c.rpc_publisher, Publisher)
        self.assertIs(c.rpc_publisher.session, rpc_session)

        c.config_changed()
        rpc_session.publish.assert_called_with(Environment.evt_opts_changed)

    def test_test_status(self, *_):
        c = self.client

        result = c.check_test_status()
        self.assertFalse(result)

        c.task_test_result = json.dumps({"status": TaskTestStatus.started})
        result = c.check_test_status()
        print(result)
        self.assertEqual(c.task_test_result, result)

        c.task_test_result = json.dumps({"status": TaskTestStatus.success})
        result = c.check_test_status()
        self.assertEqual(c.task_test_result, None)

    def test_create_task(self, *_):
        t = DummyTask(total_tasks=10, owner=Node(node_name="node_name"),
                      task_definition=DummyTaskDefinition())

        c = self.client
        c.enqueue_new_task = Mock()
        c.create_task(DictSerializer.dump(t))
        self.assertTrue(c.enqueue_new_task.called)

    def test_delete_task(self, *_):
        c = self.client
        c.remove_task_header = Mock()
        c.remove_task = Mock()
        c.task_server = Mock()

        task_id = str(uuid.uuid4())
        c.delete_task(task_id)
        assert c.remove_task_header.called
        assert c.remove_task.called
        assert c.task_server.task_manager.delete_task.called
        c.remove_task.assert_called_with(task_id)

    def test_purge_tasks(self, *_):
        c = self.client
        c.remove_task_header = Mock()
        c.remove_task = Mock()
        c.task_server = Mock()

        task_id = str(uuid.uuid4())
        c.get_tasks = Mock(return_value=[{'id': task_id}, ])

        c.purge_tasks()
        assert c.get_tasks.called
        assert c.remove_task_header.called
        assert c.remove_task.called
        assert c.task_server.task_manager.delete_task.called
        c.remove_task.assert_called_with(task_id)

    def test_get_unsupport_reasons(self, *_):
        c = self.client
        c.task_server.task_keeper.get_unsupport_reasons = Mock()
        c.task_server.task_keeper.get_unsupport_reasons.return_value = [
            {'avg': '17.0.0', 'reason': 'app_version', 'ntasks': 3},
            {'avg': 7, 'reason': 'max_price', 'ntasks': 2},
            {'avg': None, 'reason': 'environment_missing', 'ntasks': 1},
            {'avg': None,
             'reason': 'environment_not_accepting_tasks', 'ntasks': 1},
            {'avg': None, 'reason': 'requesting_trust', 'ntasks': 0},
            {'avg': None, 'reason': 'deny_list', 'ntasks': 0},
            {'avg': None, 'reason': 'environment_unsupported', 'ntasks': 0}]
        c.task_archiver.get_unsupport_reasons = Mock()
        c.task_archiver.get_unsupport_reasons.side_effect = lambda days: [
            {'avg': str(days * 21) + '.0.0',
             'reason': 'app_version', 'ntasks': 3},
            {'avg': 7, 'reason': 'max_price', 'ntasks': 2},
            {'avg': None, 'reason': 'environment_missing', 'ntasks': 1},
            {'avg': None,
             'reason': 'environment_not_accepting_tasks', 'ntasks': 1},
            {'avg': None, 'reason': 'requesting_trust', 'ntasks': 0},
            {'avg': None, 'reason': 'deny_list', 'ntasks': 0},
            {'avg': None, 'reason': 'environment_unsupported', 'ntasks': 0}]

        # get_unsupport_reasons(0) is supposed to read current stats from
        # the task_keeper and should not look into archives
        reasons = c.get_unsupport_reasons(0)
        self.assertEqual(reasons[0]["avg"], "17.0.0")
        c.task_server.task_keeper.get_unsupport_reasons.assert_called_with()
        c.task_archiver.get_unsupport_reasons.assert_not_called()

        c.task_server.task_keeper.get_unsupport_reasons.reset_mock()
        c.task_archiver.get_unsupport_reasons.reset_mock()

        # for more days it's the opposite
        reasons = c.get_unsupport_reasons(2)
        self.assertEqual(reasons[0]["avg"], "42.0.0")
        c.task_archiver.get_unsupport_reasons.assert_called_with(2)
        c.task_server.task_keeper.get_unsupport_reasons.assert_not_called()

        # and for a negative number of days we should get an exception
        with self.assertRaises(ValueError):
            reasons = c.get_unsupport_reasons(-1)

    def test_task_preview(self, *_):
        task_id = str(uuid.uuid4())
        c = self.client
        c.task_server.task_manager.tasks[task_id] = Mock()
        c.task_server.task_manager.get_task_preview = Mock()

        c.get_task_preview(task_id)
        c.task_server.task_manager.get_task_preview.assert_called_with(
            task_id, single=False
        )

    def test_task_stats(self, *_):
        c = self.client

        result = c.get_task_stats()
        expected = {
            'host_state': "Idle",
            'provider_state': {'status': 'idle'},
            'in_network': 0,
            'supported': 0,
            'subtasks_computed': (0, 0),
            'subtasks_with_errors': (0, 0),
            'subtasks_with_timeout': (0, 0)
        }

        self.assertEqual(result, expected)

    def test_subtasks_borders(self, *_):
        task_id = str(uuid.uuid4())
        c = self.client
        c.task_server.task_manager.tasks[task_id] = Mock()
        c.task_server.task_manager.get_subtasks_borders = Mock()

        c.get_subtasks_borders(task_id)
        c.task_server.task_manager.get_subtasks_borders.assert_called_with(
            task_id, 1
        )

    def test_connection_status(self, *_):
        c = self.client

        # not connected
        self.assertTrue(
            c.connection_status().startswith("Application not listening")
        )

        # status without peers
        c.p2pservice.cur_port = 12345
        c.task_server.cur_port = 12346

        # status without peers
        self.assertTrue(c.connection_status().startswith("Not connected"))

        # peers
        c.p2pservice.incoming_peers = {
            str(i): self.__new_incoming_peer()
            for i in range(3)
        }
        c.p2pservice.peers = {str(i): self.__new_session() for i in range(4)}

        known_peers = c.get_known_peers()
        self.assertEqual(len(known_peers), 3)
        self.assertTrue(all(peer for peer in known_peers))

        connected_peers = c.get_connected_peers()
        self.assertEqual(len(connected_peers), 4)
        self.assertTrue(all(peer for peer in connected_peers))

        # status with peers
        self.assertTrue(c.connection_status().startswith("Connected"))

        # status without ports
        c.p2pservice.cur_port = 0
        self.assertTrue(
            c.connection_status().startswith("Application not listening")
        )

    def test_provider_status_starting(self, *_):
        # given
        self.client.task_server = None

        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'golem is starting',
        }
        assert status == expected_status

    def test_provider_status_computing(self, *_):
        # given
        task_computer = Mock()
        state_snapshot_dict = {
            'subtask_id': str(uuid.uuid4()),
            'progress': 0.0,
            'seconds_to_timeout': 0.0,
            'running_time_seconds': 0.0,
            'outfilebasename': "Test Task",
            'output_format': "PNG",
            'scene_file': "/golem/resources/cube.blend",
            'frames': [1],
            'start_task': 1,
            'end_task': 1,
            'total_tasks': 1,
        }
        task_computer.get_progress.return_value = \
            ComputingSubtaskStateSnapshot(**state_snapshot_dict)
        self.client.task_server.task_computer = task_computer

        # when
        status = self.client.get_provider_status()

        # then
        state_snapshot_dict['scene_file'] = "cube.blend"
        expected_status = {
            'status': 'computing',
            'subtask': state_snapshot_dict,
        }
        assert status == expected_status

    def test_provider_status_waiting_for_task(self, *_):
        # given
        task_computer = Mock()
        task_computer.get_progress.return_value = None
        task_computer.waiting_for_task = str(uuid.uuid4())
        self.client.task_server.task_computer = task_computer

        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'waiting for task',
            'task_id_waited_for': task_computer.waiting_for_task,
        }
        assert status == expected_status

    def test_provider_status_not_accepting_tasks(self, *_):
        # given
        self.client.config_desc.accept_tasks = False

        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'not accepting tasks',
        }
        assert status == expected_status

    def test_provider_status_idle(self, *_):
        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'idle',
        }
        assert status == expected_status

    def test_golem_version(self, *_):
        assert self.client.get_golem_version() == golem.__version__

    def test_golem_status(self, *_):
        status = 'component', 'method', 'stage', 'data'

        # no statuses published
        assert not self.client.get_golem_status()

        # status published, no rpc publisher
        StatusPublisher.publish(*status)
        assert not self.client.get_golem_status()

        # status published, with rpc publisher
        StatusPublisher._rpc_publisher = Mock()
        StatusPublisher.publish(*status)
        assert self.client.get_golem_status() == status

    def test_port_status(self, *_):
        port = random.randint(1, 65535)
        self.assertIsNone(self.client.node.port_statuses.get(port))

        dispatcher.send(
            signal="golem.p2p",
            event="no event at all",
            port=port,
            description="timeout"
        )
        self.assertIsNone(self.client.node.port_statuses.get(port))

        dispatcher.send(
            signal="golem.p2p",
            event="unreachable",
            port=port,
            description="timeout"
        )
        self.assertEqual(self.client.node.port_statuses.get(port), "timeout")

    def test_get_performance_values(self, *_):
        expected_perf = {DefaultEnvironment.get_id(): 0.0}
        assert self.client.get_performance_values() == expected_perf

    def test_block_node(self, *_):
        self.client.task_server.acl = Mock(spec=Acl)
        self.client.block_node('node_id')
        self.client.task_server.acl.disallow.assert_called_once_with(
            'node_id', persist=True)

    def test_run_test_task_success(self, *_):
        result = {'result': 'result'}
        estimated_memory = 1234
        time_spent = 1.234
        more = {'more': 'more'}

        def _run(_self: TaskTester):
            self.assertIsInstance(self.client.task_test_result, str)
            test_result = json.loads(self.client.task_test_result)
            self.assertEqual(test_result, {
                "status": TaskTestStatus.started,
                "error": True
            })

            _self.success_callback(result, estimated_memory, time_spent, **more)

        with patch.object(self.client.task_server.task_manager, 'create_task'),\
                patch('golem.client.TaskTester.run', _run):
            self.client._run_test_task({})

        self.assertIsInstance(self.client.task_test_result, str)
        test_result = json.loads(self.client.task_test_result)
        self.assertEqual(test_result, {
            "status": TaskTestStatus.success,
            "result": result,
            "estimated_memory": estimated_memory,
            "time_spent": time_spent,
            "more": more
        })

    def test_run_test_task_error(self, *_):
        error = ['error', 'error']
        more = {'more': 'more'}

        def _run(_self: TaskTester):
            self.assertIsInstance(self.client.task_test_result, str)
            test_result = json.loads(self.client.task_test_result)
            self.assertEqual(test_result, {
                "status": TaskTestStatus.started,
                "error": True
            })

            _self.error_callback(*error, **more)

        with patch.object(self.client.task_server.task_manager, 'create_task'),\
                patch('golem.client.TaskTester.run', _run):
            self.client._run_test_task({})

        self.assertIsInstance(self.client.task_test_result, str)
        test_result = json.loads(self.client.task_test_result)
        self.assertEqual(test_result, {
            "status": TaskTestStatus.error,
            "error": error,
            "more": more
        })

    @classmethod
    def __new_incoming_peer(cls):
        return dict(node=cls.__new_session())

    @staticmethod
    def __new_session():
        session = Mock()
        for attr in PeerSessionInfo.attributes:
            setattr(session, attr, str(uuid.uuid4()))
        return session


def test_task_computer_event_listener():
    client = Mock()
    listener = ClientTaskComputerEventListener(client)

    listener.lock_config(True)
    client.lock_config.assert_called_with(True)

    listener.lock_config(False)
    client.lock_config.assert_called_with(False)


class TestDepositBalance(TestClientBase):
    @freeze_time("2018-01-01 01:00:00")
    def test_unlocking(self, *_):
        self.client.transaction_system.concent_timelock\
            .return_value = int(time.time())
        with freeze_time("2018-01-01 00:59:59"):
            result = sync_wait(self.client.get_deposit_balance())
        self.assertEqual(result['status'], 'unlocking')

    @freeze_time("2018-01-01 01:00:00")
    def test_unlocked(self, *_):
        self.client.transaction_system.concent_timelock\
            .return_value = int(time.time())
        with freeze_time("2018-01-01 01:00:01"):
            result = sync_wait(self.client.get_deposit_balance())
        self.assertEqual(result['status'], 'unlocked')

    def test_locked(self, *_):
        self.client.transaction_system.concent_timelock\
            .return_value = 0
        result = sync_wait(self.client.get_deposit_balance())
        self.assertEqual(result['status'], 'locked')


class DepositPaymentsListTest(TestClientBase):
    def test_empty(self):
        self.assertEqual(self.client.get_deposit_payments_list(), [])

    def test_one(self):
        tx_hash = \
            '0x5e9880b3e9349b609917014690c7a0afcdec6dbbfbef3812b27b60d246ca10ae'
        value = 31337
        ts = 1514761200.0
        dt = datetime.datetime.fromtimestamp(ts)
        model.DepositPayment.create(
            value=value,
            tx=tx_hash,
            created_date=dt,
            modified_date=dt,
        )
        expected = [
            {
                'created': ts,
                'modified': ts,
                'fee': None,
                'status': 'awaiting',
                'transaction': tx_hash,
                'value': str(value),
            },
        ]
        self.assertEqual(
            expected,
            self.client.get_deposit_payments_list(),
        )


class TestClientPEP8(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        "golem/client.py",
    ]
