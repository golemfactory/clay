# pylint: disable=protected-access,too-many-lines
import os
import time
import uuid
from random import Random
from unittest import TestCase
from unittest.mock import (
    ANY,
    create_autospec,
    MagicMock,
    Mock,
    patch,
)

from ethereum.utils import denoms
from freezegun import freeze_time
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from pydispatch import dispatcher
from twisted.internet.defer import Deferred, inlineCallbacks

from golem import model
from golem import testutils
from golem.appconfig import (
    DEFAULT_HYPERDRIVE_RPC_PORT, DEFAULT_HYPERDRIVE_RPC_ADDRESS
)
from golem.client import Client, ClientTaskComputerEventListener, \
    DoWorkService, MonitoringPublisherService, \
    NetworkConnectionPublisherService, \
    ResourceCleanerService, TaskArchiverService, \
    TaskCleanerService
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.config.active import EthereumConfig
from golem.core.common import timeout_to_string
from golem.core.deferred import sync_wait
from golem.core.variables import CONCENT_CHOICES
from golem.hardware.presets import HardwarePresets
from golem.manager.nodestatesnapshot import ComputingSubtaskStateSnapshot
from golem.network.p2p.peersession import PeerSessionInfo
from golem.report import StatusPublisher
from golem.resource.dirmanager import DirManager
from golem.rpc.mapping.rpceventnames import UI, Environment, Golem
from golem.task import taskstate
from golem.task.acl import Acl
from golem.task.taskcomputer import TaskComputer
from golem.task.taskserver import TaskServer
from golem.task.taskmanager import TaskManager
from golem.testutils import DatabaseFixture
from golem.tools import testwithreactor
from golem.tools.assertlogs import LogTestCase

from tests.factories import model as model_factory
from tests.factories.task import taskstate as taskstate_factory

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
    return ets


@patch('golem.client.node_info_str')
@patch(
    'golem.network.concent.handlers_library.HandlersLibrary'
    '.register_handler',
)
@patch('signal.signal')
@patch('golem.network.p2p.local_node.LocalNode.collect_network_info')
def make_client(*_, **kwargs):
    config_desc = ClientConfigDescriptor()
    config_desc.max_memory_size = 1024 * 1024  # 1 GiB
    config_desc.num_cores = 1
    config_desc.hyperdrive_rpc_address = DEFAULT_HYPERDRIVE_RPC_ADDRESS
    config_desc.hyperdrive_rpc_port = DEFAULT_HYPERDRIVE_RPC_PORT
    default_kwargs = {
        'app_config': Mock(),
        'config_desc': config_desc,
        'keys_auth': Mock(
            _private_key=b'a' * 32,
            key_id='a' * 64,
            public_key=b'a' * 128,
        ),
        'database': Mock(),
        'transaction_system': Mock(),
        'connect_to_known_hosts': False,
        'use_docker_manager': False,
        'use_monitor': False,
        'concent_variant': CONCENT_CHOICES['disabled'],
    }
    default_kwargs.update(kwargs)
    client = Client(**default_kwargs)
    return client


class TestClientBase(DatabaseFixture):

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

    def test_withdraw(self, *_):
        ets = self.client.transaction_system
        ets.return_value = ets
        ets.return_value.eth_base_for_batch_payment.return_value = 0
        self.client.withdraw('123', '0xdead', 'ETH', 123)
        ets.withdraw.assert_called_once_with(123, '0xdead', 'ETH', 123)

    def test_get_withdraw_gas_cost(self, *_):
        dest = '0x' + 40 * '0'
        ets = Mock()
        ets = self.client.transaction_system
        self.client.get_withdraw_gas_cost('123', dest, 'ETH')
        ets.get_withdraw_gas_cost.assert_called_once_with(123, dest, 'ETH')

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

    def test_quit(self, *_):
        self.client.db = None
        self.client.quit()

    @patch('golem.client.TaskCleanerService.start')
    def test_task_cleaning_disabled(self, task_cleaner, *_):
        self.client.config_desc.cleaning_enabled = 0
        self.client.config_desc.clean_tasks_older_than_seconds = 0

        self.client.start_network()

        task_cleaner.assert_not_called()

    @patch('golem.client.TaskCleanerService.start')
    def test_task_cleaning_enabled(self, task_cleaner, *_):
        self.client.config_desc.cleaning_enabled = 1
        self.client.config_desc.clean_tasks_older_than_seconds = 1

        self.client.start_network()

        task_cleaner.assert_called()

    def test_collect_gossip(self, *_):
        self.client.start_network()
        self.client.collect_gossip()

    def test_activate_hw_preset(self, *_):
        config = self.client.config_desc

        HardwarePresets.initialize(self.client.datadir)
        HardwarePresets.update_config('default', config)

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

    def test_restore_locks(self, *_):
        tm = Mock()
        self.client.task_server = Mock(task_manager=tm)
        self.client.funds_locker = Mock()
        tm.tasks_states = {
            "t1": Mock(status=taskstate.TaskStatus.finished),
            "t2": Mock(
                status=taskstate.TaskStatus.computing,
                subtask_states={
                    "sub1": taskstate_factory.SubtaskState(
                        status=taskstate.SubtaskStatus.finished,
                    ),
                    "sub2": taskstate_factory.SubtaskState(
                        status=taskstate.SubtaskStatus.failure,
                    ),
                },
            ),
        }
        subtask_price = 123
        tm.tasks = {
            "t2": Mock(
                subtask_price=subtask_price,
                get_total_tasks=Mock(return_value=3)
            ),
        }
        self.client._restore_locks()
        self.client.funds_locker.lock_funds.assert_called_once_with(
            "t2",
            subtask_price,
            2,
        )


class TestClientRestartSubtasks(TestClientBase):

    def setUp(self):
        super().setUp()
        self.ts = self.client.transaction_system

        self.task_id = "test_task_id"
        self.subtask_price = 100

        self.client.funds_locker.lock_funds(
            self.task_id,
            self.subtask_price,
            10,
        )

        self.client.task_server = Mock()

    def test_restart_subtask(self):
        # given
        self.client.task_server.task_manager.get_task_id.return_value = \
            self.task_id

        # when
        self.client.restart_subtask('subtask_id')

        # then
        self.client.task_server.task_manager.restart_subtask.\
            assert_called_with('subtask_id')
        self.ts.lock_funds_for_payments.assert_called_with(
            self.subtask_price, 1)


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
            assert self.do_work_service._check_ts[
                key] == time.time() + interval

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
        assert send.call_count == 5


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
@patch('golem.network.p2p.local_node.LocalNode.collect_network_info')
class TestClientRPCMethods(TestClientBase, LogTestCase):
    # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self.client.sync = Mock()
        self.client.p2pservice = Mock(peers={})
        self.client.apps_manager._benchmark_enabled = Mock(return_value=True)
        self.client.apps_manager.load_all_apps()
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler', ):
            self.client.task_server = TaskServer(
                node=dt_p2p_factory.Node(),
                config_desc=self.client.config_desc,
                client=self.client,
                use_docker_manager=False,
                apps_manager=self.client.apps_manager,
            )
        self.client.monitor = Mock()
        self.client._update_hw_preset = Mock()
        self.client.task_server.change_config = Mock()

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

    def test_get_balance(self, *_):
        c = self.client
        ethconfig = EthereumConfig()

        c.transaction_system = Mock(
            contract_addresses=ethconfig.CONTRACT_ADDRESSES
        )

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
            'contract_addresses': {
                contract.name: address
                for contract, address
                in ethconfig.CONTRACT_ADDRESSES.items()
            }
        }
        assert all(isinstance(entry, str) for entry in balance)

    def test_run_benchmark(self, *_):
        from apps.blender.blenderenvironment import BlenderEnvironment
        from apps.blender.benchmark.benchmark import BlenderBenchmark

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

        assert benchmark_manager.run_benchmark.call_count == 1

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
        HardwarePresets.initialize(self.client.datadir)

        new_node_name = str(uuid.uuid4())
        self.assertNotEqual(c.get_setting('node_name'), new_node_name)

        c.update_setting('node_name', new_node_name)
        self.assertEqual(c.get_setting('node_name'), new_node_name)
        self.assertEqual(c.get_settings()['node_name'], new_node_name)
        c._update_hw_preset.assert_not_called()

        c.update_setting('hardware_preset_name', 'custom')
        c._update_hw_preset.assert_called_once()

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

        c.task_test_result = {"status": taskstate.TaskTestStatus.started}
        result = c.check_test_status()
        self.assertEqual(
            {"status": taskstate.TaskTestStatus.started.value},
            result,
        )

    def test_delete_task(self, *_):
        c = self.client
        c.remove_task_header = Mock()
        c.remove_task = Mock()
        c.task_server = Mock()

        task_id = str(uuid.uuid4())
        c.delete_task(task_id)
        assert c.task_server.remove_task_header.called
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
        assert c.task_server.remove_task_header.called
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
            'provider_state': {'status': 'Idle'},
            'in_network': 0,
            'supported': 0,
            'subtasks_computed': (0, 0),
            'subtasks_accepted': (0, 0),
            'subtasks_rejected': (0, 0),
            'subtasks_with_errors': (0, 0),
            'subtasks_with_timeout': (0, 0)
        }

        self.assertEqual(result, expected)

    def test_connection_status_not_listening(self, *_):
        c = self.client

        # when
        status = c.connection_status()

        # then
        assert not status['listening']

        msg = status['msg']
        assert "not listening" in msg
        assert "Not connected" not in msg
        assert "Connected" not in msg

    def test_connection_status_without_peers(self, *_):
        c = self.client

        # given
        c.p2pservice.cur_port = 12345
        c.task_server.cur_port = 12346

        # when
        status = c.connection_status()

        # then
        assert status['listening']
        assert not status['connected']

        msg = status['msg']
        assert "not listening" not in msg
        assert "Not connected" in msg
        assert "Connected" not in msg

    def test_connection_status_with_peers(self, *_):
        c = self.client

        # given
        c.p2pservice.cur_port = 12345
        c.task_server.cur_port = 12346
        c.p2pservice.peers = {str(i): self.__new_session() for i in range(4)}

        # when
        status = c.connection_status()

        # then
        assert status['listening']
        assert status['connected']

        msg = status['msg']
        assert "not listening" not in msg
        assert "Not connected" not in msg
        assert "Connected" in msg

    def test_connection_status_port_statuses(self, *_):
        c = self.client

        # given
        c.p2pservice.cur_port = 12345
        c.task_server.cur_port = 12346
        c.p2pservice.peers = {str(i): self.__new_session() for i in range(4)}

        port_statuses = {
            1234: "open",
            2345: "unreachable",
        }
        c.node.port_statuses = port_statuses

        # when
        status = c.connection_status()

        # then
        assert status['port_statuses'] == port_statuses

        msg = status['msg']
        assert "not listening" not in msg
        assert "Not connected" not in msg
        assert "Connected" in msg
        assert "Port(s)" in msg
        assert "1234: open" in msg
        assert "2345: unreachable" in msg

    def test_get_known_peers(self, *_):
        c = self.client

        # given
        c.p2pservice.incoming_peers = {
            str(i): self.__new_incoming_peer()
            for i in range(3)
        }

        # when
        known_peers = c.get_known_peers()

        # then
        self.assertEqual(len(known_peers), 3)
        self.assertTrue(all(peer for peer in known_peers))

    def test_get_connected_peers(self, *_):
        c = self.client

        # given
        c.p2pservice.peers = {str(i): self.__new_session() for i in range(4)}

        # when
        connected_peers = c.get_connected_peers()

        # then
        self.assertEqual(len(connected_peers), 4)
        self.assertTrue(all(peer for peer in connected_peers))
        self.assertIsInstance(connected_peers[0]['node_info'], dict)

    def test_provider_status_starting(self, *_):
        # given
        self.client.task_server = None

        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'Golem is starting',
        }
        assert status == expected_status

    def test_provider_status_computing(self, *_):
        # given
        start_task = 1
        task_computer = Mock()
        state_snapshot_dict = {
            'subtask_id': str(uuid.uuid4()),
            'progress': 0.0,
            'seconds_to_timeout': 0.0,
            'running_time_seconds': 0.0,
            'outfilebasename': "Test Task_{}".format(start_task),
            'output_format': "PNG",
            'scene_file': "/golem/resources/cube.blend",
            'frames': [1],
            'start_task': start_task,
            'total_tasks': 1,
        }
        task_computer.get_progress.return_value = \
            ComputingSubtaskStateSnapshot(**state_snapshot_dict)
        self.client.task_server.task_computer = task_computer

        # environment
        environment = task_computer.get_environment()

        # when
        status = self.client.get_provider_status()

        # then
        state_snapshot_dict['scene_file'] = "cube.blend"
        expected_status = {
            'environment': environment,
            'status': 'Computing',
            'subtask': state_snapshot_dict,
        }
        assert status == expected_status

    def test_provider_status_not_accepting_tasks(self, *_):
        # given
        self.client.config_desc.accept_tasks = False

        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'Not accepting tasks',
        }
        assert status == expected_status

    def test_provider_status_idle(self, *_):
        # when
        status = self.client.get_provider_status()

        # then
        expected_status = {
            'status': 'Idle',
        }
        assert status == expected_status

    def test_golem_status_no_publisher(self, *_):
        component = 'component'
        status = 'method', 'stage', {'status': 'message', 'value': 'data'}

        # status published, no rpc publisher
        StatusPublisher.publish(component, *status)
        assert self.client.get_golem_status()[component] == status

    @inlineCallbacks
    def test_golem_status_with_publisher(self, *_):
        component = 'component'
        status = 'method', 'stage', {'status': 'message', 'value': 'data'}

        # status published, with rpc publisher
        StatusPublisher._rpc_publisher = Mock()
        deferred: Deferred = StatusPublisher.publish(component, *status)
        assert self.client.get_golem_status()[component] == status

        yield deferred

        assert StatusPublisher._rpc_publisher.publish.called
        call = StatusPublisher._rpc_publisher.publish.call_args
        assert call[0][0] == Golem.evt_golem_status
        assert call[0][1][component] == status

    def test_port_status_open(self, *_):
        port = random.randint(1, 65535)
        self.assertIsNone(self.client.node.port_statuses.get(port))

        dispatcher.send(
            signal="golem.p2p",
            event="open",
            port=port,
            description="open"
        )
        self.assertEqual(self.client.node.port_statuses.get(port), "open")

    def test_port_status_unreachable(self, *_):
        port = random.randint(1, 65535)
        self.assertIsNone(self.client.node.port_statuses.get(port))

        dispatcher.send(
            signal="golem.p2p",
            event="unreachable",
            port=port,
            description="timeout"
        )
        self.assertEqual(self.client.node.port_statuses.get(port), "timeout")

    def test_port_status_other(self, *_):
        port = random.randint(1, 65535)
        self.assertIsNone(self.client.node.port_statuses.get(port))

        dispatcher.send(
            signal="golem.p2p",
            event="unreachable",
            port=port,
            description="timeout"
        )
        self.assertEqual(self.client.node.port_statuses.get(port), "timeout")

    def test_block_node(self, *_):
        self.client.task_server.acl = Mock(spec=Acl)
        self.client.block_node('node_id')
        self.client.task_server.acl.disallow.assert_called_once_with(
            'node_id', -1, True)

    @classmethod
    def __new_incoming_peer(cls):
        return dict(node=cls.__new_session())

    @staticmethod
    def __new_session():
        session = Mock()
        for attr in PeerSessionInfo.attributes:
            setattr(session, attr, str(uuid.uuid4()))
        session.node_info = dt_p2p_factory.Node()
        return session


def test_task_computer_event_listener():
    client = Mock()
    listener = ClientTaskComputerEventListener(client)

    listener.lock_config(True)
    client.lock_config.assert_called_with(True)

    listener.lock_config(False)
    client.lock_config.assert_called_with(False)


@patch('golem.terms.ConcentTermsOfUse.are_accepted', return_value=True)
class TestDepositBalance(TestClientBase):
    def test_no_concent(self, *_):
        self.client.concent_service.variant = CONCENT_CHOICES['disabled']
        self.assertFalse(self.client.concent_service.available)
        self.client.transaction_system.concent_timelock.side_effect\
            = Exception("Let's pretend there's no such contract")
        self.assertIsNone(sync_wait(self.client.get_deposit_balance()))

    @freeze_time("2018-01-01 01:00:00")
    def test_unlocking(self, *_):
        self.client.concent_service.variant = CONCENT_CHOICES['test']
        self.assertTrue(self.client.concent_service.available)
        self.client.transaction_system.concent_timelock\
            .return_value = int(time.time())
        with freeze_time("2018-01-01 00:59:59"):
            result = sync_wait(self.client.get_deposit_balance())
        self.assertEqual(result['status'], 'unlocking')

    @freeze_time("2018-01-01 01:00:00")
    def test_unlocked(self, *_):
        self.client.concent_service.variant = CONCENT_CHOICES['test']
        self.assertTrue(self.client.concent_service.available)
        self.client.transaction_system.concent_timelock\
            .return_value = int(time.time())
        with freeze_time("2018-01-01 01:00:01"):
            result = sync_wait(self.client.get_deposit_balance())
        self.assertEqual(result['status'], 'unlocked')

    def test_locked(self, *_):
        self.client.concent_service.variant = CONCENT_CHOICES['test']
        self.assertTrue(self.client.concent_service.available)
        self.client.transaction_system.concent_timelock\
            .return_value = 0
        result = sync_wait(self.client.get_deposit_balance())
        self.assertEqual(result['status'], 'locked')


@patch(
    'golem.network.concent.client.ConcentClientService.__init__',
    return_value=None,
)
class TestConcentInitialization(TestClientBase):
    def setUp(self):
        super(TestClientBase, self).setUp()  # pylint: disable=bad-super-call

    @patch('golem.network.concent.client.ConcentClientService.stop')
    def tearDown(self, *_):  # pylint: disable=arguments-differ
        super().tearDown()

    def test_no_contract(self, CCS, *_):
        self.client = make_client(
            datadir=self.path,
            transaction_system=Mock(deposit_contract_available=False),
            concent_variant=CONCENT_CHOICES['test'],
        )
        CCS.assert_called_once_with(
            keys_auth=ANY,
            variant=CONCENT_CHOICES['disabled'],
        )


class TestGetTask(TestClientBase):
    def test_all_sent(self):
        self.client.task_server = create_autospec(TaskServer)
        self.client.task_server.task_manager = create_autospec(TaskManager)
        self.client.task_server.task_computer = create_autospec(TaskComputer)
        self.client.transaction_system.get_subtasks_payments.return_value \
            = [
                model_factory.TaskPayment(
                    wallet_operation__status=model.WalletOperation.STATUS.sent,
                ),
                model_factory.TaskPayment(
                    wallet_operation__status=model.WalletOperation.STATUS.sent,
                    wallet_operation__gas_cost=1,
                ),
            ]
        self.client.get_task(uuid.uuid4())


class TestClientPEP8(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        "golem/client.py",
    ]
