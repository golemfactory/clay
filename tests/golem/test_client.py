import os
import time
import unittest
import uuid

from mock import Mock, MagicMock, patch
from twisted.internet.defer import Deferred

from golem import testutils
from golem.client import Client, ClientTaskComputerEventListener, log
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.simpleserializer import DictSerializer
from golem.core.deferred import sync_wait
from golem.model import Payment, PaymentStatus
from golem.network.p2p.node import Node
from golem.network.p2p.peersession import PeerSessionInfo
from golem.resource.dirmanager import DirManager
from golem.resource.resourceserver import ResourceServer
from golem.rpc.mapping.aliases import UI, Environment
from golem.task.taskbase import Task, TaskHeader, resource_types
from golem.task.taskcomputer import TaskComputer
from golem.task.taskmanager import TaskManager
from golem.task.taskserver import TaskServer
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithdatabase import TestWithDatabase


class TestCreateClient(TestDirFixture, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/client.py', ]

    @patch('twisted.internet.reactor', create=True)
    def test_config_override_valid(self, *_):
        self.assertTrue(hasattr(ClientConfigDescriptor(), "node_address"))
        c = Client(datadir=self.path, node_address='1.0.0.0',
                   transaction_system=False, connect_to_known_hosts=False,
                   use_docker_machine_manager=False,
                   use_monitor=False)
        self.assertEqual(c.config_desc.node_address, '1.0.0.0')
        c.quit()

    @patch('twisted.internet.reactor', create=True)
    def test_config_override_invalid(self, *_):
        """Test that Client() does not allow to override properties
        that are not in ClientConfigDescriptor.
        """
        self.assertFalse(hasattr(ClientConfigDescriptor(), "node_colour"))
        with self.assertRaises(AttributeError):
            Client(datadir=self.path, node_colour='magenta',
                   transaction_system=False, connect_to_known_hosts=False,
                   use_docker_machine_manager=False,
                   use_monitor=False)


@patch('signal.signal')
@patch('golem.network.p2p.node.Node.collect_network_info')
class TestClient(TestWithDatabase):

    def tearDown(self):
        if hasattr(self, 'client'):
            self.client.quit()

    def test_get_payments(self, *_):
        self.client = Client(datadir=self.path, transaction_system=True,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False, use_monitor=False)

        payments = [
            Payment(subtask=uuid.uuid4(),
                    status=PaymentStatus.awaiting,
                    payee=str(uuid.uuid4()),
                    value=2 * 10 ** 18,
                    created=time.time(),
                    modified=time.time())
            for _ in xrange(2)
        ]

        db = Mock()
        db.get_newest_payment.return_value = payments

        self.client.transaction_system.payments_keeper.db = db
        received_payments = self.client.get_payments_list()

        self.assertEqual(len(received_payments), len(payments))

        for i in xrange(len(payments)):
            self.assertEqual(received_payments[i]['subtask'],
                             payments[i].subtask)
            self.assertEqual(received_payments[i]['status'],
                             payments[i].status.value)
            self.assertEqual(received_payments[i]['payee'],
                             unicode(payments[i].payee))
            self.assertEqual(received_payments[i]['value'],
                             unicode(payments[i].value))

    def test_payment_address(self, *_):
        self.client = Client(datadir=self.path, transaction_system=True,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False, use_monitor=False)

        payment_address = self.client.get_payment_address()
        self.assertIsInstance(payment_address, unicode)
        self.assertTrue(len(payment_address) > 0)

    @patch('golem.transactions.ethereum.ethereumtransactionsystem.'
           'EthereumTransactionSystem.sync')
    def test_sync(self, *_):
        self.client = Client(datadir=self.path, transaction_system=True,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False, use_monitor=False)
        self.client.sync()
        # TODO: assertTrue when re-enabled
        self.assertFalse(self.client.transaction_system.sync.called)

    def test_remove_resources(self, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)

        def unique_dir():
            d = os.path.join(self.path, str(uuid.uuid4()))
            if not os.path.exists(d):
                os.makedirs(d)
            return d

        c = self.client
        c.task_server = Mock()
        c.task_server.get_task_computer_root.return_value = unique_dir()
        c.task_server.task_manager.get_task_manager_root.return_value = unique_dir()

        c.resource_server = Mock()
        c.resource_server.get_distributed_resource_root.return_value = unique_dir()

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
        self.client = Client(datadir=datadir, transaction_system=False,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False, use_monitor=False)

        self.assertEqual(self.client.config_desc.node_address, '')
        with self.assertRaises(IOError):
            Client(datadir=datadir)

    def test_metadata(self, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False, use_monitor=False)

        meta = self.client.get_metadata()
        self.assertIsNotNone(meta)
        self.assertEqual(meta, dict())

    def test_description(self, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)

        self.assertEqual(self.client.get_description(), "")
        desc = u"ADVANCE DESCRIPTION\n\tSOME TEXT"
        self.client.change_description(desc)
        self.assertEqual(self.client.get_description(), desc)

    @unittest.skip('IPFS metadata is currently disabled')
    def test_interpret_metadata(self, *_):
        from golem.network.ipfs.daemon_manager import IPFSDaemonManager
        from golem.network.p2p.p2pservice import P2PService

        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False)

        self.client.p2pservice = P2PService(MagicMock(), self.client.config_desc, self.client.keys_auth)
        self.client.ipfs_manager = IPFSDaemonManager()
        meta = self.client.get_metadata()
        assert meta and meta['ipfs']

        ip = '127.0.0.1'
        port = 40102

        node = MagicMock()
        node.prv_addr = ip
        node.prv_port = port

        self.client.interpret_metadata(meta, ip, port, node)

    def test_get_status(self, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)
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
        c.task_server.task_computer.get_progresses.return_value = {"id1": mock1, "id2": mock2}
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

    @patch('twisted.internet.reactor', create=True)
    def test_collect_gossip(self, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False,
                             use_monitor=False)
        self.client.start_network()
        self.client.collect_gossip()

    @patch('golem.client.log')
    def test_do_work(self, log, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False,
                             use_docker_machine_manager=False,
                             use_monitor=False)

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

        c._Client__do_work()

        assert c.p2pservice.ping_peers.called
        assert log.exception.call_count == 5

    @patch('golem.client.log')
    @patch('golem.client.dispatcher.send')
    def test_publish_events(self, send, log, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)
        c = self.client

        def get_balance(*_):
            d = Deferred()
            d.callback((1, 2, 3))
            return d

        c.task_server = Mock()
        c.task_server.task_computer = TaskComputer.__new__(TaskComputer)
        c.task_server.task_computer.stats = dict()

        c.get_balance = get_balance
        c.get_task_count = lambda *_: 0
        c.get_supported_task_count = lambda *_: 0
        c.connection_status = lambda *_: 'test'

        c.config_desc.node_snapshot_interval = 1
        c.config_desc.network_check_interval = 1

        c._publish = Mock()

        past_time = time.time() - 10 ** 10
        future_time = time.time() + 10 ** 10

        c.last_nss_time = future_time
        c.last_net_check_time = future_time
        c.last_balance_time = future_time
        c.last_tasks_time = future_time

        c._Client__publish_events()

        assert not send.called
        assert not log.debug.called
        assert not c._publish.called

        c.last_nss_time = past_time
        c.last_net_check_time = past_time
        c.last_balance_time = past_time
        c.last_tasks_time = past_time

        c._Client__publish_events()

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

        c._Client__publish_events()

        assert log.debug.called
        assert send.call_count == 2
        assert c._publish.call_count == 2

    def test_activate_hw_preset(self, *_):
        self.client = Client(datadir=self.path, transaction_system=False,
                             connect_to_known_hosts=False, use_docker_machine_manager=False,
                             use_monitor=False)

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




@patch('signal.signal')
@patch('golem.network.p2p.node.Node.collect_network_info')
class TestClientRPCMethods(TestWithDatabase, LogTestCase):

    def setUp(self):
        super(TestClientRPCMethods, self).setUp()

        client = Client(datadir=self.path,
                        transaction_system=False,
                        connect_to_known_hosts=False,
                        use_docker_machine_manager=False,
                        use_monitor=False)

        client.sync = Mock()
        client.p2pservice = Mock()
        client.p2pservice.peers = {}
        client.task_server = Mock()
        client.monitor = Mock()

        self.client = client

    def tearDown(self):
        self.client.quit()

    def test_node(self, *_):
        c = self.client
        self.assertIsInstance(c.get_node(), dict)
        self.assertIsInstance(DictSerializer.load(c.get_node()), Node)

        self.assertIsInstance(c.get_node_key(), unicode)
        self.assertIsNotNone(c.get_node_key())

        c.node.key = None

        self.assertNotIsInstance(c.get_node_key(), unicode)
        self.assertIsNone(c.get_node_key())

        self.assertIsInstance(c.get_public_key(), bytes)
        self.assertEqual(c.get_public_key(), c.keys_auth.public_key)

    def test_directories(self, *_):
        c = self.client

        self.assertIsInstance(c.get_datadir(), unicode)
        self.assertIsInstance(c.get_dir_manager(), Mock)

        c.task_server = TaskServer.__new__(TaskServer)
        c.task_server.client = self.client
        c.task_server.task_manager = TaskManager.__new__(TaskManager)
        c.task_server.task_manager.root_path = self.path
        c.task_server.task_computer = TaskComputer.__new__(TaskComputer)
        c.task_server.task_computer.dir_manager = DirManager(self.tempdir)
        c.task_server.task_computer.current_computations = []

        c.resource_server = ResourceServer.__new__(ResourceServer)
        c.resource_server.dir_manager = c.task_server.task_computer.dir_manager

        self.assertIsInstance(c.get_dir_manager(), DirManager)

        res_dirs = c.get_res_dirs()

        self.assertIsInstance(res_dirs, dict)
        self.assertTrue(len(res_dirs) == 3)

        for key, value in res_dirs.iteritems():
            self.assertIsInstance(key, unicode)
            self.assertIsInstance(value, unicode)
            self.assertTrue(self.path in value)

        res_dir_sizes = c.get_res_dirs_sizes()

        for key, value in res_dir_sizes.iteritems():
            self.assertIsInstance(key, unicode)
            self.assertIsInstance(value, unicode)
            self.assertTrue(key in res_dirs)

    def test_enqueue_new_task(self, *_):
        c = self.client
        c.resource_server = Mock()
        c.keys_auth = Mock()
        c.keys_auth.key_id = str(uuid.uuid4())

        c.task_server = TaskServer.__new__(TaskServer)
        c.task_server.client = c
        c.task_server.task_computer = Mock()
        c.task_server.task_manager = TaskManager.__new__(TaskManager)
        c.task_server.task_manager.add_new_task = Mock()
        c.task_server.task_manager.root_path = self.path

        task = Mock()
        task.header.max_price = 1 * 10 ** 18
        task.header.task_id = str(uuid.uuid4())

        c.enqueue_new_task(task)
        task.get_resources.assert_called_with(None, resource_types["hashes"])
        c.resource_server.resource_manager.build_client_options.assert_called_with(c.keys_auth.key_id)
        assert c.resource_server.add_task.called
        assert not c.task_server.task_manager.add_new_task.called

        deferred = Deferred()
        deferred.callback(True)

        c.resource_server.add_task.called = False
        c.resource_server.add_task.return_value = deferred

        c.enqueue_new_task(task)
        assert c.resource_server.add_task.called
        assert c.task_server.task_manager.add_new_task.called

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
            'subtask_count': '6',
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

        c.task_server = TaskServer.__new__(TaskServer)
        c.task_server.client = c
        c.task_server.task_computer = Mock()
        c.task_server.task_manager = TaskManager('node_name', Mock(),
                                                 c.keys_auth)
        c.task_server.task_manager.add_new_task = Mock()
        c.task_server.task_manager.root_path = self.path

        task = c.enqueue_new_task(t_dict)
        assert isinstance(task, Task)
        assert task.header.task_id

        c.resource_server.resource_manager.build_client_options\
            .assert_called_with(c.keys_auth.key_id)
        assert c.resource_server.add_task.called
        assert not c.task_server.task_manager.add_new_task.called

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
        assert balance == (u"1", u"1", u"None")
        assert all(isinstance(entry, unicode) for entry in balance)

        c.transaction_system = None
        balance = sync_wait(c.get_balance())
        assert balance == (None, None, None)

    def test_run_benchmark(self, *_):
        from apps.blender.blenderenvironment import BlenderEnvironment
        from apps.lux.luxenvironment import LuxRenderEnvironment

        task_computer = self.client.task_server.task_computer
        task_computer.run_blender_benchmark.side_effect = lambda c, e: c(True)
        task_computer.run_lux_benchmark.side_effect = lambda c, e: c(True)

        with self.assertRaises(Exception):
            sync_wait(self.client.run_benchmark(str(uuid.uuid4())))

        sync_wait(self.client.run_benchmark(BlenderEnvironment.get_id()))

        assert task_computer.run_blender_benchmark.called
        assert not task_computer.run_lux_benchmark.called

        task_computer.run_blender_benchmark.called = False
        task_computer.run_lux_benchmark.called = False

        sync_wait(self.client.run_benchmark(LuxRenderEnvironment.get_id()))

        assert not task_computer.run_blender_benchmark.called
        assert task_computer.run_lux_benchmark.called

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

    def test_create_task(self, *_):
        c = self.client
        c.enqueue_new_task = Mock()

        # create a task
        t = Task(TaskHeader("node_name", "task_id",
                            "10.10.10.10", 123,
                            "owner_id", "DEFAULT"),
                 src_code="print('hello')")

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
        c.get_task_preview(task_id)
        c.task_server.task_manager.get_task_preview.assert_called_with(
            task_id, single=False)

    def test_subtasks_borders(self, *_):
        task_id = str(uuid.uuid4())
        c = self.client
        c.get_subtasks_borders(task_id)
        c.task_server.task_manager.get_subtasks_borders.assert_called_with(
            task_id)

    def test_connection_status(self, *_):
        c = self.client

        # status without peers
        self.assertTrue(c.connection_status().startswith(u"Not connected"))

        # peers
        c.p2pservice.free_peers = [self.__new_session() for _ in xrange(3)]
        c.p2pservice.peers = {str(i): self.__new_session() for i in xrange(4)}

        known_peers = c.get_known_peers()
        self.assertEqual(len(known_peers), 3)
        self.assertTrue(all(peer for peer in known_peers))

        connected_peers = c.get_connected_peers()
        self.assertEqual(len(connected_peers), 4)
        self.assertTrue(all(peer for peer in connected_peers))

        # status with peers
        self.assertTrue(c.connection_status().startswith(u"Connected"))

        # status without ports
        c.p2pservice.cur_port = 0
        self.assertTrue(c.connection_status().startswith(u"Application not listening"))

    def test_port_status(self, *_):
        from pydispatch import dispatcher
        import random
        random.seed()

        port = random.randint(1, 50000)
        self.assertFalse(self.client.node.port_status)
        dispatcher.send(signal="golem.p2p", event="no event at all", port=port,
                        description="port 1234: closed")
        self.assertFalse(self.client.node.port_status)
        dispatcher.send(signal="golem.p2p", event="unreachable", port=port,
                        description="port 1234: closed")
        self.assertTrue(self.client.node.port_status)

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
