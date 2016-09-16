import os
import unittest
import uuid

from ethereum.utils import denoms
from golem.task.taskmanager import TaskManager

from golem.task.taskcomputer import TaskComputer
from mock import Mock, MagicMock, patch

from gnr.gnrapplicationlogic import GNRClientRemoteEventListener
from golem.client import Client, GolemClientRemoteEventListener, ClientTaskComputerEventListener
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.ethereum.paymentmonitor import IncomingPayment
from golem.network.p2p.node import Node
from golem.resource.dirmanager import DirManager
from golem.task.taskserver import TaskServer
from golem.task.taskstate import ComputerState
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithdatabase import TestWithDatabase


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
        assert isinstance(c.get_node(), Node)

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

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_update_setting(self, _):
        c = self.__new_client()
        new_node_name = str(uuid.uuid4())
        c.update_setting('node_name', new_node_name)
        assert c.config_desc.node_name == new_node_name

    @patch('golem.network.p2p.node.Node.collect_network_info')
    def test_get_tasks(self, _):
        c = self.__new_client()

        c.task_server = TaskServer.__new__(TaskServer)
        c.task_server.task_manager = TaskManager.__new__(TaskManager)
        c.task_server.task_computer = TaskComputer.__new__(TaskComputer)
        c.task_server.task_computer.dir_manager = DirManager(self.tempdir)
        c.task_server.task_computer.current_computations = []

        count = 3

        tasks, tasks_states, task_id, subtask_id = self.__build_tasks(count)

        c.task_server.task_manager.tasks = tasks
        c.task_server.task_manager.tasks_states = tasks_states
        c.task_server.task_manager.subtask2task_mapping = self.__build_subtask2task(tasks)

        one_task = c.get_tasks(task_id)
        assert one_task
        assert isinstance(one_task, dict)
        assert len(one_task)

        all_tasks = c.get_tasks()

        assert all_tasks
        assert isinstance(all_tasks, list)
        assert len(all_tasks) ==  count
        assert all([isinstance(t, dict) for t in all_tasks])

        one_subtask = c.get_subtask(subtask_id)

        assert one_subtask
        assert isinstance(one_subtask, dict)
        assert len(one_subtask)

        task_subtasks = c.get_subtasks(task_id)

        assert task_subtasks
        assert isinstance(task_subtasks, list)
        assert all([isinstance(t, dict) for t in task_subtasks])

    @classmethod
    def __build_tasks(cls, n):

        tasks = dict()
        tasks_states = dict()
        task_id = None
        subtask_id = None

        for i in xrange(0, n):

            task = Mock()
            task.header.task_id = str(uuid.uuid4())
            task.get_total_tasks.return_value = i + 2
            task.get_progress.return_value = i * 10

            state = Mock()
            state.status = 'waiting'
            state.remaining_time = 100 - i

            subtask_states, subtask_id = cls.__build_subtasks(n)

            state.subtask_states = subtask_states
            task.subtask_states = subtask_states

            task_id = task.header.task_id

            tasks[task.header.task_id] = task
            tasks_states[task.header.task_id] = state

        return tasks, tasks_states, task_id, subtask_id

    @staticmethod
    def __build_subtasks(n):

        subtasks = dict()
        subtask_id = None

        for i in xrange(0, n):

            subtask = Mock()
            subtask.subtask_id = str(uuid.uuid4())
            subtask.computer = ComputerState()
            subtask.computer.node_name = 'node_{}'.format(i)
            subtask.computer.node_id = 'deadbeef0{}'.format(i)
            subtask_id = subtask.subtask_id

            subtasks[subtask.subtask_id] = subtask

        return subtasks, subtask_id

    @staticmethod
    def __build_subtask2task(tasks):
        subtask2task = dict()
        for k, t in tasks.items():
            print k, t.subtask_states
            for sk, st in t.subtask_states.items():
                subtask2task[st.subtask_id] = t
        return subtask2task

    def __new_client(self):
        client = Client(datadir=self.path,
                        transaction_system=False,
                        connect_to_known_hosts=False,
                        use_docker_machine_manager=False,
                        use_monitor=False)

        client.p2pservice = Mock()
        client.task_server = Mock()
        client.monitor = Mock()

        return client


class TestEventListener(unittest.TestCase):

    def test_remote_event_listener(self):

        builder = Mock()
        builder.build_client = lambda x: Mock()
        listener = GolemClientRemoteEventListener(Mock())

        assert listener.build(builder)
        assert listener.remote_client

        gnr_listener = GNRClientRemoteEventListener(Mock())

        assert gnr_listener.build(builder)
        assert gnr_listener.remote_client

        gnr_listener.task_updated('xyz')
        assert gnr_listener.remote_client.task_status_changed.called

        gnr_listener.check_network_state()
        assert gnr_listener.remote_client.check_network_state.called

    def test_task_computer_event_listener(self):

        client = Mock()
        listener = ClientTaskComputerEventListener(client)

        listener.toggle_config_dialog(True)
        client.toggle_config_dialog.assert_called_with(True)

        listener.toggle_config_dialog(False)
        client.toggle_config_dialog.assert_called_with(False)
