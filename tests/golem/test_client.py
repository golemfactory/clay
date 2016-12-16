import os
import unittest
import uuid

from ethereum.utils import denoms
from golem.client import Client, ClientTaskComputerEventListener
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.simpleserializer import DictSerializer
from golem.ethereum.paymentmonitor import IncomingPayment
from golem.network.p2p.node import Node
from golem.network.p2p.peersession import PeerSessionInfo
from golem.resource.dirmanager import DirManager
from golem.task.taskcomputer import TaskComputer
from golem.task.taskmanager import TaskManager
from golem.task.taskserver import TaskServer
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithdatabase import TestWithDatabase
from mock import Mock, MagicMock, patch


class TestCreateClient(TestDirFixture):

    def test_config_override_valid(self):
        assert hasattr(ClientConfigDescriptor(), "node_address")
        c = Client(datadir=self.path, node_address='1.0.0.0',
                   transaction_system=False, connect_to_known_hosts=False,
                   use_docker_machine_manager=False,
                   use_monitor=False)
        assert c.config_desc.node_address == '1.0.0.0'
        c.quit()

    def test_config_override_invalid(self):
        """Test that Client() does not allow to override properties
        that are not in ClientConfigDescriptor.
        """
        assert not hasattr(ClientConfigDescriptor(), "node_colour")
        with self.assertRaises(AttributeError):
            Client(datadir=self.path, node_colour='magenta',
                   transaction_system=False, connect_to_known_hosts=False,
                   use_docker_machine_manager=False,
                   use_monitor=False)


class TestClient(TestWithDatabase):

    def test_payment_func(self):
        c = Client(datadir=self.path, transaction_system=True, connect_to_known_hosts=False,
                   use_docker_machine_manager=False, use_monitor=False)
        c.transaction_system.add_to_waiting_payments("xyz", "ABC", 10)
        incomes = c.transaction_system.get_incomes_list()
        self.assertEqual(len(incomes), 1)
        self.assertEqual(incomes[0]["node"], "ABC")
        self.assertEqual(incomes[0]["expected_value"], 10.0)
        self.assertEqual(incomes[0]["task"], "xyz")
        self.assertEqual(incomes[0]["value"], 0.0)

        c.transaction_system.pay_for_task("xyz", [])
        c.check_payments()
        c.transaction_system.check_payments = Mock()
        c.transaction_system.check_payments.return_value = ["ABC", "DEF"]
        c.check_payments()

        assert c.get_incomes_list() == []
        payment = IncomingPayment("0x00003", 30 * denoms.ether)
        payment.extra = {'block_number': 311,
                         'block_hash': "hash1",
                         'tx_hash': "hash2"}
        c.transaction_system._EthereumTransactionSystem__monitor._PaymentMonitor__payments.append(payment)
        incomes = c.get_incomes_list()
        assert len(incomes) == 1
        assert incomes[0]['block_number'] == 311
        assert incomes[0]['value'] == 30 * denoms.ether
        assert incomes[0]['payer'] == "0x00003"

        c.quit()

    def test_remove_resources(self):
        c = Client(datadir=self.path, transaction_system=False,
                   connect_to_known_hosts=False, use_docker_machine_manager=False,
                   use_monitor=False)

        def unique_dir():
            d = os.path.join(self.path, str(uuid.uuid4()))
            if not os.path.exists(d):
                os.makedirs(d)
            return d

        c.task_server = Mock()
        c.task_server.get_task_computer_root.return_value = unique_dir()
        c.task_server.task_manager.get_task_manager_root.return_value = unique_dir()

        c.resource_server = Mock()
        c.resource_server.get_distributed_resource_root.return_value = unique_dir()

        d = c.get_computed_files_dir()
        assert self.path in d
        self.additional_dir_content([3], d)
        c.remove_computed_files()
        assert not os.listdir(d)

        d = c.get_distributed_files_dir()
        assert self.path in os.path.normpath(d)  # normpath for mingw
        self.additional_dir_content([3], d)
        c.remove_distributed_files()
        assert not os.listdir(d)

        d = c.get_received_files_dir()
        assert self.path in d
        self.additional_dir_content([3], d)
        c.remove_received_files()
        assert not os.listdir(d)
        c.quit()

    def test_datadir_lock(self):
        # Let's use non existing dir as datadir here to check how the Client
        # is able to cope with that.
        datadir = os.path.join(self.path, "non-existing-dir")
        c = Client(datadir=datadir, transaction_system=False,
                   connect_to_known_hosts=False, use_docker_machine_manager=False, use_monitor=False)
        assert c.config_desc.node_address == ''
        with self.assertRaises(IOError):
            Client(datadir=datadir)
        c.quit()

    def test_metadata(self):
        c = Client(datadir=self.path, transaction_system=False,
                   connect_to_known_hosts=False, use_docker_machine_manager=False, use_monitor=False)
        meta = c.get_metadata()
        assert meta is not None
        assert not meta
        c.quit()

    def test_description(self):
        c = Client(datadir=self.path, transaction_system=False,
                   connect_to_known_hosts=False, use_docker_machine_manager=False,
                   use_monitor=False)
        assert c.get_description() == ""
        desc = u"ADVANCE DESCRIPTION\n\tSOME TEXT"
        c.change_description(desc)
        assert c.get_description() == desc
        c.quit()

    # FIXME: IPFS metadata disabled
    # def test_interpret_metadata(self):
    #     from golem.network.ipfs.daemon_manager import IPFSDaemonManager
    #     c = Client(datadir=self.path, transaction_system=False,
    #                connect_to_known_hosts=False, use_docker_machine_manager=False)
    #     c.p2pservice = P2PService(MagicMock(), c.config_desc, c.keys_auth)
    #     c.ipfs_manager = IPFSDaemonManager()
    #     meta = c.get_metadata()
    #     assert meta and meta['ipfs']
    #
    #     ip_1 = '127.0.0.1'
    #     port_1 = 40102
    #
    #     node = MagicMock()
    #     node.prv_addr = ip_1
    #     node.prv_port = port_1
    #
    #     c.interpret_metadata(meta, ip_1, port_1, node)
    #     c.quit()

    def test_get_status(self):
        c = Client(datadir=self.path, transaction_system=False,
                   connect_to_known_hosts=False, use_docker_machine_manager=False,
                   use_monitor=False)
        c.task_server = MagicMock()
        c.task_server.task_computer.get_progresses.return_value = {}
        c.p2pservice = MagicMock()
        c.p2pservice.get_peers.return_value = ["ABC", "DEF"]
        c.transaction_system = MagicMock()
        status = c.get_status()
        assert "Waiting for tasks" in status
        assert "Active peers in network: 2" in status
        mock1 = MagicMock()
        mock1.get_progress.return_value = 0.25
        mock2 = MagicMock()
        mock2.get_progress.return_value = 0.33
        c.task_server.task_computer.get_progresses.return_value = {"id1": mock1, "id2": mock2}
        c.p2pservice.get_peers.return_value = []
        status = c.get_status()
        assert "Computing 2 subtask(s)" in status
        assert "id1 (25.0%)" in status
        assert "id2 (33.0%)" in status
        assert "Active peers in network: 0" in status
        c.config_desc.accept_tasks = 0
        status = c.get_status()
        assert "Computing 2 subtask(s)" in status
        c.task_server.task_computer.get_progresses.return_value = {}
        status = c.get_status()
        assert "Not accepting tasks" in status
        c.quit()

    def test_quit(self):
        c = Client(datadir=self.path)
        c.db = None
        c.quit()


class TestClientRPCMethods(TestWithDatabase):

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_node(self, _):
        c = self.__new_client()
        assert isinstance(c.get_node(), dict)
        assert isinstance(DictSerializer.load(c.get_node()), Node)
        c.quit()

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_dir_manager(self, _):
        c = self.__new_client()
        assert isinstance(c.get_dir_manager(), Mock)

        c.task_server = TaskServer.__new__(TaskServer)
        c.task_server.task_manager = TaskManager.__new__(TaskManager)
        c.task_server.task_computer = TaskComputer.__new__(TaskComputer)
        c.task_server.task_computer.dir_manager = DirManager(self.tempdir)
        c.task_server.task_computer.current_computations = []

        assert isinstance(c.get_dir_manager(), DirManager)
        c.quit()

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_misc(self, _):
        c = self.__new_client()
        c.enqueue_new_task = Mock()

        try:
            # settings
            new_node_name = str(uuid.uuid4())
            assert c.get_setting('node_name') != new_node_name
            c.update_setting('node_name', new_node_name)
            assert c.get_setting('node_name') == new_node_name
            assert c.get_settings()['node_name'] == new_node_name

            newer_node_name = str(uuid.uuid4())
            assert c.get_setting('node_name') != newer_node_name
            settings = c.get_settings()
            settings['node_name'] = newer_node_name
            c.update_settings(settings)
            assert c.get_setting('node_name') == newer_node_name

            # configure rpc
            rpc_session = Mock()
            assert c.rpc_publisher is None
            c.configure_rpc(rpc_session)
            assert c.rpc_publisher.session is rpc_session

            # create task rpc
            task_dict = dict(_cls=('golem.task.taskbase', 'Task'), should_wait=False)
            c.create_task(task_dict)
            assert c.enqueue_new_task.called

            # status without peers
            assert c.connection_status().startswith(u"Not connected")

            # peers
            c.p2pservice.free_peers = [self.__new_session() for _ in xrange(3)]
            c.p2pservice.peers = {str(i): self.__new_session() for i in xrange(4)}

            known_peers = c.get_known_peers()
            assert len(known_peers) == 3
            assert all(peer for peer in known_peers)

            connected_peers = c.get_connected_peers()
            assert len(connected_peers) == 4
            assert all(peer for peer in connected_peers)

            # status with peers
            assert c.connection_status().startswith(u"Connected")
            # status without ports
            c.p2pservice.cur_port = 0
            assert c.connection_status().startswith(u"Application not listening")

            # public key
            assert c.get_public_key() == c.keys_auth.public_key

        except:
            raise
        finally:
            c.quit()

    @staticmethod
    def __new_session():
        session = Mock()
        for attr in PeerSessionInfo.attributes:
            setattr(session, attr, str(uuid.uuid4()))
        return session

    def __new_client(self):
        client = Client(datadir=self.path,
                        transaction_system=True,
                        connect_to_known_hosts=False,
                        use_docker_machine_manager=False,
                        use_monitor=False)

        client.p2pservice = Mock()
        client.p2pservice.peers = {}
        client.task_server = Mock()
        client.monitor = Mock()

        return client


class TestEventListener(unittest.TestCase):

    def test_task_computer_event_listener(self):

        client = Mock()
        listener = ClientTaskComputerEventListener(client)

        listener.lock_config(True)
        client.lock_config.assert_called_with(True)

        listener.lock_config(False)
        client.lock_config.assert_called_with(False)
