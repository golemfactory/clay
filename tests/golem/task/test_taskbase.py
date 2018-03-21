# pylint: disable=no-self-use
from unittest import TestCase
import unittest.mock as mock

from golem.core.simpleserializer import CBORSerializer
from golem.docker.image import DockerImage
from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskBuilder, TaskHeader
from golem.tools.assertlogs import LogTestCase


@mock.patch.multiple(Task, __abstractmethods__=frozenset())
class TestTaskBase(LogTestCase):
    def test_header_serialization(self):
        node = Node(node_name="test node")
        docker_images = [
            dict(
                repository="repo_{}".format(i),
                id="id_{}".format(i),
                tag="tag_{}".format(i)
            )
            for i in range(4)
        ]

        task_header = TaskHeader(
            "ABC", "xyz", "10.10.10.10", 1023, "key", "DEFAULT",
            task_owner=node)
        # ignore dynamic properties
        task_header.last_checking = 0

        task_header_dict = task_header.to_dict()
        serialized = CBORSerializer.dumps(task_header_dict)
        deserialized = CBORSerializer.loads(serialized)
        task_header_from_dict = TaskHeader.from_dict(deserialized)

        # ignore dynamic properties
        task_header_from_dict.last_checking = 0

        assert task_header_from_dict.to_dict() == task_header_dict
        assert isinstance(task_header_from_dict.task_owner, Node)

        task_header_bin = task_header.to_binary()
        bin_serialized = CBORSerializer.dumps(task_header_bin)
        bin_deserialized = CBORSerializer.loads(bin_serialized)

        assert bin_deserialized == task_header_bin


class TestTaskBuilder(TestCase):
    def test_build_definition(self) -> None:
        TaskBuilder.build_definition("testtask", {"resources": []})
