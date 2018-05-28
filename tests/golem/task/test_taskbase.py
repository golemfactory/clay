# pylint: disable=no-self-use
import time
from datetime import datetime
from unittest import TestCase
import unittest.mock as mock

import golem
from golem.core.common import timeout_to_deadline, get_timestamp_utc
from golem.core.idgenerator import generate_id
from golem.core.simpleserializer import CBORSerializer
from golem.docker.image import DockerImage
from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskBuilder, TaskHeader
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex


@mock.patch.multiple(Task, __abstractmethods__=frozenset())
class TestTaskBase(LogTestCase):
    def test_header_serialization(self):
        node = Node(node_name="test node",
                    pub_addr="10.10.10.10",
                    pub_port=1023)

        task_header = TaskHeader(
            task_id="xyz", environment="DEFAULT", task_owner=node)
        # ignore dynamic properties
        task_header.fixed_header.last_checking = 0

        task_header_dict = task_header.to_dict()
        serialized = CBORSerializer.dumps(task_header_dict)
        deserialized = CBORSerializer.loads(serialized)
        task_header_from_dict = TaskHeader.from_dict(deserialized)

        # ignore dynamic properties
        task_header_from_dict.fixed_header.last_checking = 0

        assert task_header_from_dict.to_dict() == task_header_dict
        assert isinstance(task_header_from_dict.task_owner, Node)

        task_header_bin = task_header.to_binary()
        bin_serialized = CBORSerializer.dumps(task_header_bin)
        bin_deserialized = CBORSerializer.loads(bin_serialized)

        assert bin_deserialized == task_header_bin


class TestTaskBuilder(TestCase):
    def test_build_definition(self) -> None:
        TaskBuilder.build_definition("testtask", {"resources": []})


class TestTaskHeader(TestCase):

    def setUp(self):
        self.key_id = b'key_id'
        self.th_dict_repr = {
            'fixed_header': {
                "task_id": generate_id(self.key_id),
                "task_owner": {
                    "node_name": "Bob's node",
                    "key": encode_hex(self.key_id),
                    "pub_addr": "10.10.10.10",
                    "pub_port": 10101
                },
                "environment": "DEFAULT",
                "last_checking": time.time(),
                "deadline": timeout_to_deadline(1201),
                "subtask_timeout": 120,
                "max_price": 10,
                "min_version": golem.__version__,
                "resource_size": 0,
                "estimated_memory": 0,
            }
        }

    def test_is_correct_ok(self):
        correct, err = TaskHeader.is_correct(self.th_dict_repr)
        self.assertTrue(correct)
        self.assertIsNone(err)

    def test_is_correct_illegal_deadline(self):
        self.th_dict_repr['fixed_header']['deadline'] = datetime.now()
        correct, err = TaskHeader.is_correct(self.th_dict_repr)
        self.assertFalse(correct)
        self.assertIn("Deadline is not a timestamp", err)

    def test_is_correct_deadline_passed(self):
        self.th_dict_repr['fixed_header']['deadline'] = get_timestamp_utc() - 10
        correct, err = TaskHeader.is_correct(self.th_dict_repr)
        self.assertFalse(correct)
        self.assertIn("Deadline already passed", err)

    def test_is_correct_illegal_timeout(self):
        self.th_dict_repr['fixed_header']['subtask_timeout'] = "abc"
        correct, err = TaskHeader.is_correct(self.th_dict_repr)
        self.assertFalse(correct)
        self.assertIn("Subtask timeout is not a number", err)

    def test_is_correct_negative_timeout(self):
        self.th_dict_repr['fixed_header']['subtask_timeout'] = -131
        correct, err = TaskHeader.is_correct(self.th_dict_repr)
        self.assertFalse(correct)
        self.assertIn("Subtask timeout is less than 0", err)

    def test_is_correct_no_fixed_header(self):
        del self.th_dict_repr['fixed_header']
        correct, err = TaskHeader.is_correct(self.th_dict_repr)
        self.assertFalse(correct)
        self.assertIn("Fixed header is missing", err)
