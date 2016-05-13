import unittest

from mock import Mock

from golem.network.transport.tcpnetwork import SocketAddress

from golem.network.transport.tcpserver import (TCPServer, PendingConnectionsServer, PendingConnection,
                                               PendingListening)
from golem.network.p2p.node import Node


class ConfigDescriptor(object):
    def __init__(self, start_port, end_port):
        self.start_port = start_port
        self.end_port = end_port


class Network(object):
    def __init__(self):
        self.stop_listening_called = False
        self.listen_called = False
        self.connected = False

    def listen(self, _):
        self.listen_called = True

    def stop_listening(self, _):
        self.stop_listening_called = True

    def connect(self, connect_info, conn_id, *args):
        self.connected = True


class TestTCPServer(unittest.TestCase):

    def __test_change_scenario(self, server, port, start_port, end_port, stop_state, listen_state):
        server.network = Network()
        server.cur_port = port
        server.change_config(ConfigDescriptor(start_port, end_port))
        self.assertEqual(server.network.stop_listening_called, stop_state)
        self.assertEqual(server.network.listen_called, listen_state)

    def test_change_config(self):
        server = TCPServer(None, Network())
        self.assertEqual(server.cur_port, 0)
        self.assertFalse(server.network.stop_listening_called)
        server.change_config(ConfigDescriptor(10, 20))
        self.assertFalse(server.network.stop_listening_called)
        self.assertTrue(server.network.listen_called)

        self.__test_change_scenario(server, 10, 10, 20, False, False)
        self.__test_change_scenario(server, 15, 10, 20, False, False)
        self.__test_change_scenario(server, 20, 10, 20, False, False)
        self.__test_change_scenario(server, 21, 10, 20, True, True)
        self.__test_change_scenario(server, 30, 10, 20, True, True)
        self.__test_change_scenario(server, 9, 10, 20, True, True)
        self.__test_change_scenario(server, 10, 10, 10, False, False)
        self.__test_change_scenario(server, 11, 10, 10, True, True)
        self.__test_change_scenario(server, 0, 10, 10, False, True)


class TestPendingConnectionServer(unittest.TestCase):
    def test_get_socket_addresses(self):
        server = PendingConnectionsServer(None, Network())

        node = Node()
        port = 100
        res = server.get_socket_addresses(node, port, None)
        self.assertEqual(res, [])
        node.pub_addr = "10.10.10.10"
        res = server.get_socket_addresses(node, port, None)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].address, node.pub_addr)
        self.assertEqual(res[0].port, port)
        node.pub_port = 1023
        res = server.get_socket_addresses(node, port, None)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].address, node.pub_addr)
        self.assertEqual(res[0].port, 1023)
        node.prv_addresses = ["10.10.10.1", "10.10.10.2", "10.10.10.3", "10.10.10.4"]
        res = server.get_socket_addresses(node, port, None)
        self.assertEqual(len(res), 5)
        self.assertEqual(res[4].address, node.pub_addr)
        self.assertEqual(res[4].port, 1023)
        for i in range(4):
            self.assertEqual(res[i].address, node.prv_addresses[i])
            self.assertEqual(res[i].port, port)
        node.pub_addr = None
        res = server.get_socket_addresses(node, port, None)
        self.assertEqual(len(res), 4)
        for i in range(4):
            self.assertEqual(res[i].address, node.prv_addresses[i])
            self.assertEqual(res[i].port, port)

    def test_pending_conn(self):
        network = Network()
        server = PendingConnectionsServer(None, network)

        server.conn_established_for_type[0] = lambda x: x
        server.conn_failure_for_type[0] = server.final_conn_failure
        server.conn_final_failure_for_type[0] = lambda x: x

        key_id = "d0d1d2"
        port = 1234

        node_info = Mock()
        node_info.prv_addresses = ["10.10.10.2"]
        node_info.pub_addr = "10.10.10.1"
        node_info.pub_port = port

        server._add_pending_request(0, node_info, port, key_id, args={})

        assert len(server.pending_connections) == 1
        server._sync_pending()
        assert len(server.pending_connections) == 0


class TestPendingConnection(unittest.TestCase):
    def test_init(self):
        pc = PendingConnection(1, "10.10.10.10")
        self.assertIsInstance(pc, PendingConnection)


class TestPendingListening(unittest.TestCase):
    def test_init(self):
        pl = PendingListening(1, 1020)
        self.assertIsInstance(pl, PendingListening)

