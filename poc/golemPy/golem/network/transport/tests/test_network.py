import unittest
import logging
import sys
import os
import time

sys.path.append(os.environ.get('GOLEM'))

from golem.network.transport.tcp_network import TCPNetwork, TCPListenInfo, TCPListeningInfo, TCPConnectInfo, TCPAddress
from golem.network.transport.network import ProtocolFactory, SessionFactory, SessionProtocol
from twisted.internet.task import deferLater
from threading import Thread


class ASession(object):
    def __init__(self, conn):
        self.conn = conn


class AProtocol(object, SessionProtocol):
    def __init__(self, server):
        self.server = server


class TestNetwork(unittest.TestCase):
    reactor_running = False
    stop_reactor = False

    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.listen_success = None
        self.connect_success = None
        self.stop_listening_success = None
        self.port = None
        self.kwargs_len = 0
        session_factory = SessionFactory(ASession)
        protocol_factory = ProtocolFactory(AProtocol, None, session_factory)
        self.network = TCPNetwork(protocol_factory)
        if not TestNetwork.reactor_running:
            TestNetwork.reactor_running = True
            th = Thread(target=self.network.reactor.run, args=(False,))
            th.deamon = True
            th.start()

    def tearDown(self):
        if TestNetwork.stop_reactor:
            self.network.reactor.stop()

    def test1__listen(self):
        listen_info = TCPListenInfo(1111, established_callback=self.__listen_success,
                                    failure_callback=self.__listen_failure)
        self.network.listen(listen_info)
        time.sleep(5)
        self.assertTrue(self.listen_success)
        self.assertEquals(self.port, 1111)

        self.network.listen(listen_info)
        time.sleep(5)
        self.assertFalse(self.listen_success)

        listen_info = TCPListenInfo(1111, 1115, established_callback=self.__listen_success,
                                   failure_callback=self.__listen_failure)
        self.network.listen(listen_info)
        time.sleep(5)
        self.assertTrue(self.listen_success)
        self.assertEquals(self.port, 1112)

        self.network.listen(listen_info, a=1, b=2, c=3, d=4, e=5)
        time.sleep(5)
        self.assertEquals(self.port, 1113)
        self.assertEquals(len(self.network.active_listeners), 3)
        self.assertEquals(self.kwargs_len, 5)

        listening_info = TCPListeningInfo(1112, self.__stop_listening_success, self.__stop_listening_failure)
        d = self.network.stop_listening(listening_info)
        time.sleep(5)
        self.assertEquals(len(self.network.active_listeners), 2)
        self.assertTrue(d.called)
        self.assertTrue(self.stop_listening_success)

        listening_info = TCPListeningInfo(1112, self.__stop_listening_success, self.__stop_listening_failure)
        d = self.network.stop_listening(listening_info)
        time.sleep(5)
        self.assertEquals(len(self.network.active_listeners), 2)
        self.assertFalse(self.stop_listening_success)


        listen_info = TCPListenInfo(1111, 1115, established_callback=self.__listen_success,
                                    failure_callback=self.__listen_failure)
        self.network.listen(listen_info)
        time.sleep(5)
        self.assertEquals(self.port, 1112)

    def test2_connect(self):
        try:
            address = TCPAddress('127.0.0.1', 1111)
            connect_info = TCPConnectInfo([address], self.__connection_success, self.__connection_failure)
            self.network.connect(connect_info)
            time.sleep(5)
            self.assertTrue(self.connect_success)

            address2 = TCPAddress('127.0.0.1', 2)
            connect_info = TCPConnectInfo([address2], self.__connection_success, self.__connection_failure)
            self.network.connect(connect_info)
            time.sleep(5)
            self.assertFalse(self.connect_success)

            connect_info.tcp_addresses.append(address2)
            connect_info.tcp_addresses.append(address)
            self.network.connect(connect_info)
            time.sleep(15)
            self.assertTrue(self.connect_success)
        finally:
            TestNetwork.stop_reactor = True

    def __listen_success(self, port, **kwargs):
        self.listen_success = True
        self.port = port
        self.kwargs_len = len(kwargs)

    def __listen_failure(self, **kwargs):
        self.listen_success = False

    def __connection_success(self, result, **kwargs):
        self.connect_success = True

    def __connection_failure(self, **kwargs):
        self.connect_success = False

    def __stop_listening_success(self, **kwargs):
        self.stop_listening_success = True

    def __stop_listening_failure(self, **kwargs):
        self.stop_listening_success = False

if __name__ == '__main__':
    unittest.main()
