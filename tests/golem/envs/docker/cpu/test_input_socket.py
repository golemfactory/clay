from socket import SocketIO, socket, SHUT_WR
from threading import RLock
from unittest import TestCase
from unittest.mock import Mock

from urllib3.contrib.pyopenssl import WrappedSocket

from golem.envs.docker.cpu import InputSocket


class TestInit(TestCase):

    def test_wrapped_socket(self):
        wrapped_sock = Mock(spec=WrappedSocket)
        input_sock = InputSocket(wrapped_sock)
        self.assertEqual(input_sock._sock, wrapped_sock)

    def test_socket_io(self):
        sock = Mock(spec=socket)
        socket_io = Mock(spec=SocketIO, _sock=sock)
        input_sock = InputSocket(socket_io)
        self.assertEqual(input_sock._sock, sock)

    def test_invalid_socket_class(self):
        with self.assertRaises(TypeError):
            InputSocket(Mock())


class TestWrite(TestCase):

    def test_ok(self):
        lock = RLock()
        sock = Mock(spec=WrappedSocket)
        sock.sendall.side_effect = lambda _: self.assertTrue(lock._is_owned())
        input_sock = InputSocket(sock)
        input_sock._lock = lock

        input_sock.write(b"test")
        sock.sendall.assert_called_once_with(b"test")


class TestClose(TestCase):

    def test_raw_socket(self):
        lock = RLock()
        sock = Mock(spec=socket)
        sock.shutdown.side_effect = lambda _: self.assertTrue(lock._is_owned())
        sock.close.side_effect = lambda: self.assertTrue(lock._is_owned())
        socket_io = Mock(spec=SocketIO, _sock=sock)
        input_sock = InputSocket(socket_io)
        input_sock._lock = lock

        input_sock.close()
        sock.shutdown.assert_called_once_with(SHUT_WR)
        sock.close.assert_called_once_with()

    def test_wrapped_socket(self):
        lock = RLock()
        sock = Mock(spec=WrappedSocket)
        sock.shutdown.side_effect = lambda: self.assertTrue(lock._is_owned())
        sock.close.side_effect = lambda: self.assertTrue(lock._is_owned())
        input_sock = InputSocket(sock)
        input_sock._lock = lock

        input_sock.close()
        sock.shutdown.assert_called_once_with()
        sock.close.assert_called_once_with()
