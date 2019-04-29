from unittest import TestCase
from unittest.mock import Mock

from golem.envs.docker.cpu import DockerInput


class TestWrite(TestCase):

    def test_raw(self):
        write = Mock()
        input_ = DockerInput(write, Mock())
        input_.write(b"test")
        write.assert_called_once_with(b"test")

    def test_encoded(self):
        write = Mock()
        input_ = DockerInput(write, Mock(), encoding="utf-8")
        input_.write("żółw")
        write.assert_called_once_with("żółw".encode("utf-8"))


class TestClose(TestCase):

    def test_close(self):
        close = Mock()
        input_ = DockerInput(Mock(), close)
        input_.close()
        close.assert_called_once()
