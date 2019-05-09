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


class TestInputSocket(TestCase):

    def _get_socket(self, socket_io=False):
        lock = RLock()

        def _assert_lock(*_, **__):
            if not lock._is_owned():
                self.fail("Socket operation performed without lock")

        sock = Mock(spec=(socket if socket_io else WrappedSocket))
        sock.sendall.side_effect = _assert_lock
        sock.shutdown.side_effect = _assert_lock
        sock.close.side_effect = _assert_lock

        wrapped_sock = Mock(spec=SocketIO, _sock=sock) if socket_io else sock
        input_sock = InputSocket(wrapped_sock)
        input_sock._lock = lock

        return sock, input_sock


class TestWrite(TestInputSocket):

    def test_ok(self):
        sock, input_sock = self._get_socket()
        input_sock.write(b"test")
        sock.sendall.assert_called_once_with(b"test")

    def test_closed(self):
        sock, input_sock = self._get_socket()
        input_sock.close()
        with self.assertRaises(RuntimeError):
            input_sock.write(b"test")
        sock.sendall.assert_not_called()


class TestClose(TestInputSocket):

    def test_socket_io(self):
        sock, input_sock = self._get_socket(socket_io=True)
        input_sock.close()
        self.assertTrue(input_sock.closed())
        sock.shutdown.assert_called_once_with(SHUT_WR)
        sock.close.assert_called_once_with()

    def test_wrapped_socket(self):
        sock, input_sock = self._get_socket(socket_io=False)
        input_sock.close()
        self.assertTrue(input_sock.closed())
        sock.shutdown.assert_called_once_with()
        sock.close.assert_called_once_with()

    def test_multiple_close(self):
        sock, input_sock = self._get_socket()
        input_sock.close()
        input_sock.close()
        self.assertTrue(input_sock.closed())
        sock.shutdown.assert_called_once()
        sock.close.assert_called_once()
