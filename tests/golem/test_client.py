from copy import copy
import os
import time
import unittest
import uuid

from mock import Mock, MagicMock, patch
from twisted.internet.defer import Deferred

from golem.client import Client, ClientTaskComputerEventListener
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timestamp_to_datetime
from golem.core.deferred import sync_wait
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.simpleserializer import DictSerializer
from golem.environments.environment import Environment as DefaultEnvironment
from golem.model import Payment, PaymentStatus, ExpectedIncome
from golem.network.p2p.node import Node
from golem.network.p2p.peersession import PeerSessionInfo
from golem.report import StatusPublisher
from golem.resource.dirmanager import DirManager
from golem.resource.resourceserver import ResourceServer
from golem.rpc.mapping.rpceventnames import UI, Environment
from golem.task.taskbase import Task, TaskHeader, ResourceType
from golem.task.taskcomputer import TaskComputer
from golem.task.taskserver import TaskServer
from golem.task.taskstate import TaskState
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.testwithreactor import TestWithReactor
from golem.utils import decode_hex, encode_hex
from golem.core.variables import APP_VERSION
from apps.appsmanager import AppsManager


def mock_async_run(req, success, error):
    try:
        result = req.method(*req.args, **req.kwargs)
    # pylint: disable=broad-except
    except Exception as e:
        error(e)
    else:
        if success:
            success(result)


def random_hex_str() -> str:
    return str(uuid.uuid4()).replace('-', '')


class TestCreateClient(TestDirFixture):
    @patch('twisted.internet.reactor', create=True)
    def test_config_override_valid(self, *_):
        self.assertTrue(hasattr(ClientConfigDescriptor(), "node_address"))
        c = Client(
            datadir=self.path,
            node_address='1.0.0.0',
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )
        self.assertEqual(c.config_desc.node_address, '1.0.0.0')
        c.quit()

    @patch('twisted.internet.reactor', create=True)
    def test_config_override_invalid(self, *_):
        """Test that Client() does not allow to override properties
        that are not in ClientConfigDescriptor.
        """
        self.assertFalse(hasattr(ClientConfigDescriptor(), "node_colour"))
        with self.assertRaises(AttributeError):
            Client(
                datadir=self.path,
                node_colour='magenta',
                transaction_system=False,
                connect_to_known_hosts=False,
                use_docker_machine_manager=False,
                use_monitor=False
            )


@patch('signal.signal')
@patch('golem.network.p2p.node.Node.collect_network_info')
class TestClient(TestWithDatabase, TestWithReactor):
    # FIXME: if we someday decide to run parallel tests,
    # this may completely break
    # pylint: disable=attribute-defined-outside-init

    def tearDown(self):
        if hasattr(self, 'client'):
            self.client.quit()

    def test_get_payments(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=True,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        n = 9
        payments = [
            Payment(
                subtask=uuid.uuid4(),
                status=PaymentStatus.awaiting,
                payee=decode_hex(random_hex_str()),
                value=i * 10**18,
                created_date=timestamp_to_datetime(i).replace(tzinfo=None),
                modified_date=timestamp_to_datetime(i).replace(tzinfo=None)
            ) for i in range(n + 1)
        ]

        db = Mock()
        db.get_newest_payment.return_value = reversed(payments)

        self.client.transaction_system.payments_keeper.db = db
        received_payments = self.client.get_payments_list()

        self.assertEqual(len(received_payments), len(payments))

        for i in range(len(payments)):
            self.assertEqual(
                received_payments[i]['subtask'], str(payments[n - i].subtask)
            )
            self.assertEqual(
                received_payments[i]['status'], payments[n - i].status.name
            )
            self.assertEqual(
                received_payments[i]['payee'],
                encode_hex(payments[n - i].payee)
            )
            self.assertEqual(
                received_payments[i]['value'], str(payments[n - i].value)
            )

    def test_get_incomes(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=True,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        n = 9
        incomes = [
            ExpectedIncome(
                sender_node=random_hex_str(),
                sender_node_details=Node(),
                task=random_hex_str(),
                subtask=random_hex_str(),
                value=i * 10**18,
                created_date=timestamp_to_datetime(i).replace(tzinfo=None),
                modified_date=timestamp_to_datetime(i).replace(tzinfo=None)
            ) for i in range(n + 1)
        ]

        for income in incomes:
            income.save()

        received_incomes = self.client.get_incomes_list()
        self.assertEqual(len(received_incomes), len(incomes))

        for i in range(len(incomes)):
            self.assertEqual(
                received_incomes[i]['subtask'], str(incomes[n - i].subtask)
            )
            self.assertEqual(
                received_incomes[i]['status'],
                str(PaymentStatus.awaiting.name)
            )
            self.assertEqual(
                received_incomes[i]['payer'], str(incomes[n - i].sender_node)
            )
            self.assertEqual(
                received_incomes[i]['value'], str(incomes[n - i].value)
            )

    def test_payment_address(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=True,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        payment_address = self.client.get_payment_address()
        self.assertIsInstance(payment_address, str)
        self.assertTrue(len(payment_address) > 0)

    @patch(
        'golem.transactions.ethereum.ethereumtransactionsystem.'
        'EthereumTransactionSystem.sync'
    )
    def test_sync(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=True,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )
        self.client.sync()
        # TODO: assertTrue when re-enabled
        self.assertFalse(self.client.transaction_system.sync.called)

    def test_remove_resources(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

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

        d = c.get_computed_files_dir()
        self.assertIn(self.path, d)
        self.additional_dir_content([3], d)
        c.remove_computed_files()
        self.assertEqual(os.listdir(d), [])

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
        self.client = Client(
            datadir=datadir,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        self.assertEqual(self.client.config_desc.node_address, '')
        with self.assertRaises(IOError):
            Client(datadir=datadir)

    def test_get_status(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )
        c = self.client
        c.task_server = MagicMock()
        c.task_server.task_computer.get_progresses.return_value = {}
        c.p2pservice = MagicMock()
        c.p2pservice.get_peers.return_value = ["ABC", "DEF"]
        c.transaction_system = MagicMock()
        status = c.get_status()
        self.assertIn("Waiting for tasks", status)
        self.assertIn("Active peers in network: 2", status)
        mock1 = MagicMock()
        mock1.get_progress.return_value = 0.25
        mock2 = MagicMock()
        mock2.get_progress.return_value = 0.33
        c.task_server.task_computer.get_progresses.return_value = \
            {"id1": mock1, "id2": mock2}
        c.p2pservice.get_peers.return_value = []
        status = c.get_status()
        self.assertIn("Computing 2 subtask(s)", status)
        self.assertIn("id1 (25.0%)", status)
        self.assertIn("id2 (33.0%)", status)
        self.assertIn("Active peers in network: 0", status)
        c.config_desc.accept_tasks = 0
        status = c.get_status()
        self.assertIn("Computing 2 subtask(s)", status)
        c.task_server.task_computer.get_progresses.return_value = {}
        status = c.get_status()
        self.assertIn("Not accepting tasks", status)

    def test_quit(self, *_):
        self.client = Client(datadir=self.path)
        self.client.db = None
        self.client.quit()

    def test_collect_gossip(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )
        self.client.start_network()
        self.client.collect_gossip()

    @patch('golem.client.log')
    def test_do_work(self, log, *_):
        # FIXME: Pylint has real problems here
        # https://github.com/PyCQA/pylint/issues/1643
        # https://github.com/PyCQA/pylint/issues/1645
        # pylint: disable=no-member
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        c = self.client
        c.sync = Mock()
        c.p2pservice = Mock()
        c.task_server = Mock()
        c.resource_server = Mock()
        c.ranking = Mock()
        c.check_payments = Mock()

        # Test if method exits if p2pservice is not present
        c.p2pservice = None
        c.config_desc.send_pings = False
        c._Client__do_work()

        assert not log.exception.called
        assert not c.check_payments.called

        # Test calls with p2pservice
        c.p2pservice = Mock()
        c.p2pservice.peers = {str(uuid.uuid4()): Mock()}

        c._Client__do_work()

        assert not c.p2pservice.ping_peers.called
        assert not log.exception.called
        assert c.p2pservice.sync_network.called
        assert c.task_server.sync_network.called
        assert c.resource_server.sync_network.called
        assert c.ranking.sync_network.called
        assert c.check_payments.called

        # Enable pings
        c.config_desc.send_pings = True

        # Make methods throw exceptions
        def raise_exc():
            raise Exception('Test exception')

        c.p2pservice.sync_network = raise_exc
        c.task_server.sync_network = raise_exc
        c.resource_server.sync_network = raise_exc
        c.ranking.sync_network = raise_exc
        c.check_payments = raise_exc

        # FIXME: Pylint doesn't handle mangled members well:
        # https://github.com/PyCQA/pylint/issues/1643
        c._Client__do_work()  # pylint: disable=no-member

        assert c.p2pservice.ping_peers.called
        assert log.exception.call_count == 5

    @patch('golem.client.log')
    @patch('golem.client.dispatcher.send')
    def test_publish_events(self, send, log, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )
        c = self.client

        def get_balance(*_):
            d = Deferred()
            d.callback((1, 2, 3))
            return d

        c.task_server = Mock()
        c.task_server.task_sessions = {str(uuid.uuid4()): Mock()}

        c.task_server.task_computer = TaskComputer.__new__(TaskComputer)
        c.task_server.task_computer.counting_thread = None
        c.task_server.task_computer.stats = dict()

        c.get_balance = get_balance
        c.get_task_count = lambda *_: 0
        c.get_supported_task_count = lambda *_: 0
        c.connection_status = lambda *_: 'test'

        c.config_desc.node_snapshot_interval = 1
        c.config_desc.network_check_interval = 1

        c._publish = Mock()

        past_time = time.time() - 10**10
        future_time = time.time() + 10**10

        c.last_nss_time = future_time
        c.last_net_check_time = future_time
        c.last_balance_time = future_time
        c.last_tasks_time = future_time

        # FIXME: Pylint doesn't handle mangled members well:
        # https://github.com/PyCQA/pylint/issues/1643
        c._Client__publish_events()  # pylint: disable=no-member

        assert not send.called
        assert not log.debug.called
        assert not c._publish.called

        c.last_nss_time = past_time
        c.last_net_check_time = past_time
        c.last_balance_time = past_time
        c.last_tasks_time = past_time

        # FIXME: Pylint doesn't handle mangled members well:
        # https://github.com/PyCQA/pylint/issues/1643
        c._Client__publish_events()  # pylint: disable=no-member

        assert not log.debug.called
        assert send.call_count == 2
        assert c._publish.call_count == 3

        def raise_exc(*_):
            raise Exception('Test exception')

        c.get_balance = raise_exc
        c._publish = Mock()
        send.call_count = 0

        c.last_nss_time = past_time
        c.last_net_check_time = past_time
        c.last_balance_time = past_time
        c.last_tasks_time = past_time

        # FIXME: Pylint doesn't handle mangled members well:
        # https://github.com/PyCQA/pylint/issues/1643
        c._Client__publish_events()  # pylint: disable=no-member

        assert log.debug.called
        assert send.call_count == 2
        assert c._publish.call_count == 2

    def test_activate_hw_preset(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

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

    def test_restart_by_frame(self, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        self.client.task_server = Mock()
        self.client.restart_frame_subtasks('tid', 10)

        self.client.task_server.task_manager.restart_frame_subtasks.\
            assert_called_with('tid', 10)

    def test_presets(self, *_):
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

    @patch('golem.client.SystemMonitor')
    @patch('golem.client.P2PService.connect_to_network')
    @patch('golem.environments.environmentsmanager.EnvironmentsManager.load_config')
    def test_start_stop(self, load_config, connect_to_network, *_):
        self.client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False
        )

        deferred = Deferred()
        connect_to_network.side_effect = lambda *_: deferred.callback(True)

        self.client.start()
        sync_wait(deferred)

        p2p_disc = self.client.p2pservice.disconnect
        task_disc = self.client.task_server.disconnect

        self.client.p2pservice.disconnect = Mock()
        self.client.p2pservice.disconnect.side_effect = p2p_disc
        self.client.task_server.disconnect = Mock()
        self.client.task_server.disconnect.side_effect = task_disc

        self.client.stop()

        assert self.client.p2pservice.disconnect.called
        assert self.client.task_server.disconnect.called


@patch('signal.signal')
@patch('golem.network.p2p.node.Node.collect_network_info')
class TestClientRPCMethods(TestWithDatabase, LogTestCase):
    def setUp(self):
        super(TestClientRPCMethods, self).setUp()

        client = Client(
            datadir=self.path,
            transaction_system=False,
            connect_to_known_hosts=False,
            use_docker_machine_manager=False,
            use_monitor=False
        )

        client.sync = Mock()
        client.keys_auth = Mock()
        client.keys_auth.key_id = str(uuid.uuid4())
        client.p2pservice = Mock()
        client.p2pservice.peers = {}
        client.task_server = TaskServer(
            Node(),
            ClientConfigDescriptor(),
            Mock(),
            client,
            use_docker_machine_manager=False
        )
        client.monitor = Mock()

        self.client = client

    def tearDown(self):
        self.client.quit()

    def test_node(self, *_):
        c = self.client
        c.keys_auth = EllipticalKeysAuth(self.path)

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

        c.resource_server = ResourceServer.__new__(ResourceServer)
        c.resource_server.dir_manager = c.task_server.task_computer.dir_manager

        self.assertIsInstance(c.get_datadir(), str)
        self.assertIsInstance(c.get_dir_manager(), DirManager)

        res_dirs = c.get_res_dirs()

        self.assertIsInstance(res_dirs, dict)
        self.assertTrue(len(res_dirs) == 3)

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
        c = self.client
        assert c.get_estimated_cost(
            "task type",
            {"price": 150,
             "subtask_time": 2.5,
             "num_subtasks": 5}
        ) == 1875

    @patch('golem.client.async_run', side_effect=mock_async_run)
    def test_enqueue_new_task(self, *_):
        c = self.client

        c.resource_server = Mock()
        c.task_server.task_manager.start_task = Mock()
        c.task_server.task_manager.listen_address = '127.0.0.1'
        c.task_server.task_manager.listen_port = 40103
        c.keys_auth = Mock()
        c.keys_auth.key_id = str(uuid.uuid4())

        task = Mock()
        task.header.max_price = 1 * 10**18
        task.header.task_id = str(uuid.uuid4())

        c.enqueue_new_task(task)
        task.get_resources.assert_called_with(None, ResourceType.HASHES)

        assert c.resource_server.resource_manager.build_client_options.called
        assert c.resource_server.add_task.called
        assert not c.task_server.task_manager.start_task.called

        deferred = Deferred()
        deferred.callback(True)
        c.task_server.task_manager.tasks.pop(task.header.task_id, None)

        c.resource_server.add_task.called = False
        c.resource_server.add_task.return_value = deferred

        c.enqueue_new_task(task)
        assert c.task_server.task_manager.start_task.called

    @patch('golem.client.async_run', side_effect=mock_async_run)
    def test_enqueue_new_task_dict(self, *_):
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

        c = self.client
        c.resource_server = Mock()
        c.keys_auth = Mock()
        c.keys_auth.key_id = str(uuid.uuid4())
        c.task_server.task_manager.add_new_task = Mock()
        c.task_server.task_manager.start_task = Mock()

        task = c.enqueue_new_task(t_dict)
        assert isinstance(task, Task)
        assert task.header.task_id

        assert c.resource_server.resource_manager.build_client_options.called
        assert c.resource_server.add_task.called
        assert c.task_server.task_manager.add_new_task.called
        assert not c.task_server.task_manager.start_task.called

        task_id = task.header.task_id
        c.task_server.task_manager.tasks[task_id] = task
        c.task_server.task_manager.tasks_states[task_id] = TaskState()
        frames = c.get_subtasks_frames(task_id)
        assert frames is not None

    @patch('golem.client.async_run')
    def test_get_balance(self, async_run, *_):
        c = self.client

        result = (None, None, None)

        deferred = Deferred()
        deferred.result = result
        deferred.called = True

        async_run.return_value = deferred

        c.transaction_system = Mock()
        c.transaction_system.get_balance.return_value = result

        balance = sync_wait(c.get_balance())
        assert balance == (None, None, None)

        result = (None, 1, None)
        deferred.result = result
        balance = sync_wait(c.get_balance())
        assert balance == (None, None, None)

        result = (1, 1, None)
        deferred.result = result
        balance = sync_wait(c.get_balance())
        assert balance == ("1", "1", "None")
        assert all(isinstance(entry, str) for entry in balance)

        c.transaction_system = None
        balance = sync_wait(c.get_balance())
        assert balance == (None, None, None)

    def test_run_benchmark(self, *_):
        from apps.blender.blenderenvironment import BlenderEnvironment
        from apps.blender.benchmark.benchmark import BlenderBenchmark
        from apps.lux.luxenvironment import LuxRenderEnvironment
        from apps.lux.benchmark.benchmark import LuxBenchmark

        benchmark_manager = self.client.task_server.benchmark_manager
        benchmark_manager.run_benchmark = Mock()
        benchmark_manager.run_benchmark.side_effect = lambda b, tb, e, c, ec: \
            c(True)

        with self.assertRaises(Exception):
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


    @patch("golem.task.benchmarkmanager.BenchmarkRunner")
    def test_run_benchmarks(self, br_mock, *_):
        benchmark_manager = self.client.task_server.benchmark_manager
        benchmark_manager.run_all_benchmarks()
        f = br_mock.call_args[0][2]  # get success callback
        f(1)
        assert br_mock.call_count == 2

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
        settings['node_name'] = newer_node_name
        with self.assertRaises(KeyError):
            c.update_settings(settings)

        del settings['py/object']
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

        c.configure_rpc(rpc_session)
        self.assertIsInstance(c.rpc_publisher, Publisher)
        self.assertIs(c.rpc_publisher.session, rpc_session)

        c.config_changed()
        rpc_session.publish.assert_called_with(Environment.evt_opts_changed)

    @patch.multiple(Task, __abstractmethods__=frozenset())
    def test_create_task(self, *_):
        c = self.client
        c.enqueue_new_task = Mock()

        # create a task
        t = Task(TaskHeader("node_name", "task_id",
                            "10.10.10.10", 123,
                            "owner_id", "DEFAULT"),
                 src_code="print('hello')",
                 task_definition=Mock())


        c.create_task(DictSerializer.dump(t))
        self.assertTrue(c.enqueue_new_task.called)

    def test_delete_task(self, *_):
        c = self.client
        c.remove_task_header = Mock()
        c.remove_task = Mock()
        c.task_server = Mock()

        c.delete_task(str(uuid.uuid4()))
        assert c.remove_task_header.called
        assert c.remove_task.called
        assert c.task_server.task_manager.delete_task.called

    def test_task_preview(self, *_):
        task_id = str(uuid.uuid4())
        c = self.client
        c.task_server.task_manager.tasks[task_id] = Mock()
        c.task_server.task_manager.get_task_preview = Mock()

        c.get_task_preview(task_id)
        c.task_server.task_manager.get_task_preview.assert_called_with(
            task_id, single=False
        )

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

    def test_golem_version(self, *_):
        assert self.client.get_golem_version() == APP_VERSION

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
        from pydispatch import dispatcher
        import random
        random.seed()

        port = random.randint(1, 50000)
        self.assertFalse(self.client.node.port_status)
        dispatcher.send(
            signal="golem.p2p",
            event="no event at all",
            port=port,
            description="port 1234: closed"
        )
        self.assertFalse(self.client.node.port_status)
        dispatcher.send(
            signal="golem.p2p",
            event="unreachable",
            port=port,
            description="port 1234: closed"
        )
        self.assertTrue(self.client.node.port_status)

    def test_get_performance_values(self, *_):
        expected_perf = {DefaultEnvironment.get_id(): 0.0}
        assert self.client.get_performance_values() == expected_perf

    @classmethod
    def __new_incoming_peer(cls):
        return dict(node=cls.__new_session())

    @staticmethod
    def __new_session():
        session = Mock()
        for attr in PeerSessionInfo.attributes:
            setattr(session, attr, str(uuid.uuid4()))
        return session


class TestEventListener(unittest.TestCase):
    def test_task_computer_event_listener(self):

        client = Mock()
        listener = ClientTaskComputerEventListener(client)

        listener.lock_config(True)
        client.lock_config.assert_called_with(True)

        listener.lock_config(False)
        client.lock_config.assert_called_with(False)
