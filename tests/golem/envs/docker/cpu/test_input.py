from socket import socket
from unittest import TestCase
from unittest.mock import Mock

from golem.envs.docker.cpu import DockerInput


class TestWrite(TestCase):

    def test_raw(self):
        sock = Mock(spec=socket)
        input_ = DockerInput(sock)
        input_.write(b"test")
        sock.sendall.assert_called_once_with(b"test")

    def test_encoded(self):
        sock = Mock(spec=socket)
        input_ = DockerInput(sock, encoding="utf-8")
        input_.write("żółw")
        sock.sendall.assert_called_once_with("żółw".encode("utf-8"))


class TestClose(TestCase):

    def test_close(self):
        sock = Mock(spec=socket)
        input_ = DockerInput(sock)
        input_.close()
        sock.close.assert_called_once()
