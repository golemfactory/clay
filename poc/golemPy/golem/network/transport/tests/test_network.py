import unittest
import logging
import sys
import os
import time

sys.path.append(os.environ.get('GOLEM'))

from golem.network.transport.tcp_network import TCPNetwork, TCPListenInfo, TCPListeningInfo, TCPConnectInfo, \
                                                TCPAddress, BasicProtocol, ServerProtocol, SafeProtocol, FilesProtocol,\
                                                MidAndFilesProtocol
from golem.network.transport.network import ProtocolFactory, SessionFactory, SessionProtocol
from golem.network.transport.Message import Message, MessageHello
from golem.core.databuffer import DataBuffer

from threading import Thread


class ASession(object):
    def __init__(self, conn):
        self.conn = conn
        self.dropped_called = False
        self.msgs = []

    def dropped(self):
        self.dropped_called = True

    def interpret(self, msg):
        self.msgs.append(msg)

    def sign(self, msg):
        msg.sig = "ASessionSign"
        return msg

    def encrypt(self, msg):
        return "ASessionEncrypt{}".format(msg)

    def decrypt(self, msg):
        if os.path.commonprefix([msg, "ASessionEncrypt"]) != "ASessionEncrypt":
            return None
        else:
            return msg[len("ASessionEncrypt"):]


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
        protocol_factory = ProtocolFactory(SafeProtocol, Server(), session_factory)
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


class Server:
    def __init__(self):
        self.new_connection_called = 0
        self.sessions = []

    def new_connection(self, session):
        self.new_connection_called += 1
        self.sessions.append(session)


class Transport:
    def __init__(self):
        self.lose_connection_called = False
        self.abort_connection_called = False
        self.buff = []

    def loseConnection(self):
        self.lose_connection_called = True

    def abortConnection(self):
        self.abort_connection_called = True

    def getHandle(self):
        pass

    def write(self, msg):
        self.buff.append(msg)


class TestProtocols(unittest.TestCase):
    def test_init(self):
        prt = [BasicProtocol(), ServerProtocol(Server()), SafeProtocol(Server())]
        for p in prt:
            from twisted.internet.protocol import Protocol
            self.assertTrue(isinstance(p, Protocol))
            self.assertFalse(p.opened)
            self.assertIsNotNone(p.db)
        for p in prt[1:]:
            self.assertIsNotNone(p.server)

    def test_close(self):
        prt = [BasicProtocol(), ServerProtocol(Server()), SafeProtocol(Server())]
        for p in prt:
            p.transport = Transport()
            self.assertFalse(p.transport.lose_connection_called)
            p.close()
            self.assertTrue(p.transport.lose_connection_called)

    def test_close_now(self):
        prt = [BasicProtocol(), ServerProtocol(Server()), SafeProtocol(Server())]
        for p in prt:
            p.transport = Transport()
            self.assertFalse(p.transport.abort_connection_called)
            p.close_now()
            self.assertFalse(p.opened)
            self.assertTrue(p.transport.abort_connection_called)

    def test_connection_made(self):
        prt = [BasicProtocol(), ServerProtocol(Server()), SafeProtocol(Server())]
        for p in prt:
            p.transport = Transport()
            session_factory = SessionFactory(ASession)
            p.set_session_factory(session_factory)
            self.assertFalse(p.opened)
            p.connectionMade()
            self.assertTrue(p.opened)
            self.assertFalse(p.session.dropped_called)
            p.connectionLost()
            self.assertFalse(p.opened)
            self.assertTrue(p.session.dropped_called)

    def test_connection_lost(self):
        prt = [BasicProtocol(), ServerProtocol(Server()), SafeProtocol(Server())]
        for p in prt:
            p.transport = Transport()
            session_factory = SessionFactory(ASession)
            p.set_session_factory(session_factory)
            self.assertIsNone(p.session)
            p.connectionLost()
            self.assertFalse(p.opened)
            p.connectionMade()
            self.assertTrue(p.opened)
            self.assertFalse(p.session.dropped_called)
            p.connectionLost()
            self.assertFalse(p.opened)
            self.assertTrue(p.session.dropped_called)


class TestBasicProtocol(unittest.TestCase):
    def test_send_and_receive_message(self):
        p = BasicProtocol()
        p.transport = Transport()
        session_factory = SessionFactory(ASession)
        p.set_session_factory(session_factory)
        self.assertFalse(p.send_message("123"))
        msg = MessageHello()
        self.assertFalse(p.send_message(msg))
        p.connectionMade()
        self.assertTrue(p.send_message(msg))
        self.assertEqual(len(p.transport.buff), 1)
        p.dataReceived(p.transport.buff[0])
        self.assertIsInstance(p.session.msgs[0], MessageHello)
        self.assertEquals(msg.timestamp, p.session.msgs[0].timestamp)
        time.sleep(1)
        msg = MessageHello()
        self.assertNotEquals(msg.timestamp, p.session.msgs[0].timestamp)
        self.assertTrue(p.send_message(msg))
        self.assertEqual(len(p.transport.buff), 2)
        db = DataBuffer()
        db.appendString(p.transport.buff[1])
        m = Message.deserialize(db)[0]
        self.assertEqual(m.timestamp, msg.timestamp)


class TestServerProtocol(unittest.TestCase):
    def test_connection_made(self):
        p = ServerProtocol(Server())
        session_factory = SessionFactory(ASession)
        p.set_session_factory(session_factory)
        p.connectionMade()
        self.assertEquals(len(p.server.sessions), 1)


class TestSaferProtocol(unittest.TestCase):
    def test_send_and_receive_message(self):
        p = SafeProtocol(Server())
        p.transport = Transport()
        session_factory = SessionFactory(ASession)
        p.set_session_factory(session_factory)
        self.assertFalse(p.send_message("123"))
        msg = MessageHello()
        self.assertEqual(msg.sig, "")
        self.assertFalse(p.send_message(msg))
        p.connectionMade()
        self.assertTrue(p.send_message(msg))
        self.assertEqual(len(p.transport.buff), 1)
        p.dataReceived(p.transport.buff[0])
        self.assertIsInstance(p.session.msgs[0], MessageHello)
        self.assertEquals(msg.timestamp, p.session.msgs[0].timestamp)
        self.assertEqual(msg.sig, "ASessionSign")

if __name__ == '__main__':
    unittest.main()
