import logging
import os
import time
import unittest
from contextlib import contextmanager

from golem.core.databuffer import DataBuffer
from golem.network.transport.message import Message, MessageHello
from golem.network.transport.network import ProtocolFactory, SessionFactory, SessionProtocol
from golem.network.transport.tcpnetwork import TCPNetwork, TCPListenInfo, TCPListeningInfo, TCPConnectInfo, \
    SocketAddress, BasicProtocol, ServerProtocol, SafeProtocol
from golem.tools.testwithreactor import TestWithReactor


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


timeout = 20


@contextmanager
def async_scope(status, idx=0):
    status[idx] = False
    started = time.time()

    yield

    while not status[idx]:
        if time.time() - started >= timeout:
            raise RuntimeError('Operation timed out')
        time.sleep(0.2)


def get_port():
    min_port = 49200
    max_port = 65535
    test_port_range = 1000
    base = int(time.time() * 10 ** 6) % (max_port - min_port - test_port_range)
    return base + min_port


class TestNetwork(TestWithReactor):
    reactor_thread = None
    prev_reactor = None
    timeout = 10

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

    def test(self):

        listen_status = [False]
        conn_status = [False, False, False]

        def _listen_success(*args, **kwargs):
            self.__listen_success(*args, **kwargs)
            listen_status[0] = True

        def _listen_failure(**kwargs):
            self.__listen_failure(**kwargs)
            listen_status[0] = True

        def _conn_success(idx):
            def fn(*args, **kwargs):
                self.__connection_success(*args, **kwargs)
                conn_status[idx] = True
            return fn

        def _conn_failure(idx):
            def fn(**kwargs):
                self.__connection_failure(**kwargs)
                conn_status[idx] = True
            return fn

        def _listen_stop_success(*args, **kwargs):
            self.__stop_listening_success(*args, **kwargs)
            listen_status[0] = True

        def _listen_stop_failure(**kwargs):
            self.__stop_listening_failure(**kwargs)
            listen_status[0] = True

        port = get_port()

        # listen

        listen_info = TCPListenInfo(port,
                                    established_callback=_listen_success,
                                    failure_callback=_listen_failure)
        with async_scope(listen_status):
            self.network.listen(listen_info)
        self.assertEquals(self.port, port)
        self.assertEquals(len(self.network.active_listeners), 1)

        listen_info = TCPListenInfo(port,
                                    established_callback=_listen_success,
                                    failure_callback=_listen_failure)
        with async_scope(listen_status):
            self.network.listen(listen_info)
        self.assertEquals(self.port, None)
        self.assertEquals(len(self.network.active_listeners), 1)

        listen_info = TCPListenInfo(port, port + 1000,
                                    established_callback=_listen_success,
                                    failure_callback=_listen_failure)
        with async_scope(listen_status):
            self.network.listen(listen_info)
        self.assertEquals(self.port, port + 1)
        self.assertEquals(len(self.network.active_listeners), 2)

        with async_scope(listen_status):
            self.network.listen(listen_info, a=1, b=2, c=3, d=4, e=5)
        self.assertEquals(self.port, port + 2)
        self.assertEquals(self.kwargs_len, 5)
        self.assertEquals(len(self.network.active_listeners), 3)

        # connect

        address = SocketAddress('localhost', port)
        connect_info = TCPConnectInfo([address], _conn_success(0), _conn_failure(0))
        self.connect_success = None

        with async_scope(conn_status, 0):
            self.network.connect(connect_info)
        self.assertTrue(self.connect_success)

        address2 = SocketAddress('localhost', port + 1)
        connect_info_2 = TCPConnectInfo([address2], _conn_success(1), _conn_failure(1))
        self.connect_success = None

        with async_scope(conn_status, 1):
            self.network.connect(connect_info_2)
        self.assertTrue(self.connect_success)

        connect_info_3 = TCPConnectInfo([address, address2], _conn_success(2), _conn_failure(2))
        self.connect_success = None

        with async_scope(conn_status, 2):
            self.network.connect(connect_info_3)
        self.assertTrue(self.connect_success)

        # stop listening

        listening_info = TCPListeningInfo(port,
                                          stopped_callback=_listen_stop_success,
                                          stopped_errback=_listen_stop_failure)
        with async_scope(listen_status):
            d = self.network.stop_listening(listening_info)

        self.assertTrue(d.called)
        self.assertEquals(len(self.network.active_listeners), 2)
        self.assertTrue(self.stop_listening_success)

        listening_info = TCPListeningInfo(port,
                                          stopped_callback=_listen_stop_success,
                                          stopped_errback=_listen_stop_failure)
        with async_scope(listen_status):
            self.network.stop_listening(listening_info)
        self.assertEquals(len(self.network.active_listeners), 2)
        self.assertFalse(self.stop_listening_success)

        listening_info = TCPListeningInfo(port + 1,
                                          stopped_callback=_listen_stop_success,
                                          stopped_errback=_listen_stop_failure)

        with async_scope(listen_status):
            self.network.stop_listening(listening_info)
        self.assertEquals(len(self.network.active_listeners), 1)
        self.assertTrue(self.stop_listening_success)

        listening_info = TCPListeningInfo(port + 2,
                                          stopped_callback=_listen_stop_success,
                                          stopped_errback=_listen_stop_failure)

        with async_scope(listen_status):
            self.network.stop_listening(listening_info)
        self.assertEquals(len(self.network.active_listeners), 0)
        self.assertTrue(self.stop_listening_success)

        # listen on previously closed ports

        listen_info = TCPListenInfo(port, port + 4,
                                    established_callback=_listen_success,
                                    failure_callback=_listen_failure)

        with async_scope(listen_status):
            self.network.listen(listen_info)
        self.assertEquals(self.port, port)
        self.assertEquals(len(self.network.active_listeners), 1)

        listening_info = TCPListeningInfo(port,
                                          stopped_callback=_listen_stop_success,
                                          stopped_errback=_listen_stop_failure)

        with async_scope(listen_status):
            self.network.stop_listening(listening_info)
        self.assertEquals(len(self.network.active_listeners), 0)

    def __listen_success(self, port, **kwargs):
        self.listen_success = True
        self.port = port
        self.kwargs_len = len(kwargs)

    def __listen_failure(self, **kwargs):
        self.port = None
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
            self.assertNotIn('session', p.__dict__)

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
            self.assertIsNotNone(p.session)
            self.assertFalse(p.session.dropped_called)
            p.connectionLost()
            self.assertFalse(p.opened)
            self.assertNotIn('session', p.__dict__)


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
        db.append_string(p.transport.buff[1])
        m = Message.deserialize(db)[0]
        self.assertEqual(m.timestamp, msg.timestamp)
        p.connectionLost()
        self.assertNotIn('session', p.__dict__)


class TestServerProtocol(unittest.TestCase):
    def test_connection_made(self):
        p = ServerProtocol(Server())
        session_factory = SessionFactory(ASession)
        p.set_session_factory(session_factory)
        p.connectionMade()
        self.assertEquals(len(p.server.sessions), 1)
        p.connectionLost()
        self.assertNotIn('session', p.__dict__)


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
        p.connectionLost()
        self.assertNotIn('session', p.__dict__)
