import unittest
from golem.network.transport.tcpserver import TCPServer


class ConfigDescriptor(object):
    def __init__(self, start_port, end_port):
        self.start_port = start_port
        self.end_port = end_port


class Network(object):
    def __init__(self):
        self.stop_listening_called = False
        self.listen_called = False

    def listen(self, _):
        self.listen_called = True

    def stop_listening(self, _):
        self.stop_listening_called = True


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
