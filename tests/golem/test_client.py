import os

from mock import Mock, MagicMock

from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.network.p2p.p2pservice import P2PService
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.testwithdatabase import TestWithDatabase


class TestCreateClient(TestDirFixture):

    def test_config_override_valid(self):
        assert hasattr(ClientConfigDescriptor(), "node_address")
        c = Client(datadir=self.path, node_address='1.0.0.0')
        assert c.config_desc.node_address == '1.0.0.0'

    def test_config_override_invalid(self):
        """Test that Client() does not allow to override properties
        that are not in ClientConfigDescriptor.
        """
        assert not hasattr(ClientConfigDescriptor(), "node_colour")
        with self.assertRaises(AttributeError):
            Client(datadir=self.path, node_colour='magenta')


class TestClient(TestWithDatabase):

    def test_payment_func(self):
        c = Client(datadir=self.path, transaction_system=True)
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
        c._unlock_datadir()

    def test_remove_resources(self):
        c = Client(datadir=self.path)
        c.start_network()

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
        c._unlock_datadir()

    def test_datadir_lock(self):
        c = Client(datadir=self.path)
        assert c.config_desc.node_address == ''
        with self.assertRaises(IOError):
            Client(datadir=self.path)
        c._unlock_datadir()

    def test_metadata(self):
        c = Client(datadir=self.path)
        meta = c.get_metadata()
        assert meta is not None
        assert not meta
        c._unlock_datadir()

    def test_interpret_metadata(self):
        from golem.network.ipfs.daemon_manager import IPFSDaemonManager
        c = Client(datadir=self.path)
        c.p2pservice = P2PService(MagicMock(), c.config_desc, c.keys_auth)
        c.ipfs_manager = IPFSDaemonManager()
        meta = c.get_metadata()
        assert meta and meta['ipfs']

        ip_1 = '127.0.0.1'
        port_1 = 40102

        node = MagicMock()
        node.prv_addr = ip_1
        node.prv_port = port_1

        c.interpret_metadata(meta, ip_1, port_1, node)
        c._unlock_datadir()

    def test_get_status(self):
        c = Client(datadir=self.path)
        c.task_server = MagicMock()
        c.task_server.task_computer.get_progresses.return_value = {}
        c.p2pservice = MagicMock()
        c.p2pservice.get_peers.return_value = ["ABC", "DEF"]
        c.transaction_system = MagicMock()
        c.transaction_system.budget = "1341"
        status = c.get_status()
        assert "Waiting for tasks" in status
        assert "Active peers in network: 2" in status
        assert "1341" in status
        mock1 = MagicMock()
        mock1.get_progress.return_value = 0.25
        mock2 = MagicMock()
        mock2.get_progress.return_value = 0.33
        c.task_server.task_computer.get_progresses.return_value = {"id1": mock1, "id2": mock2}
        c.p2pservice.get_peers.return_value = []
        c.transaction_system.budget = 31
        status = c.get_status()
        assert "Computing 2 subtask(s)" in status
        assert "id1 (25.0%)" in status
        assert "id2 (33.0%)" in status
        assert "Active peers in network: 0" in status
        assert "31" in status
        c.config_desc.accept_tasks = 0
        status = c.get_status()
        assert "Computing 2 subtask(s)" in status
        c.task_server.task_computer.get_progresses.return_value = {}
        status = c.get_status()
        assert "Not accepting tasks" in status
        c._unlock_datadir()
