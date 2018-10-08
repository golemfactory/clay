# pylint: disable=no-self-use
import time
from datetime import datetime
from unittest import TestCase
import unittest.mock as mock

from golem_messages import idgenerator

import golem
from golem.core.common import timeout_to_deadline, get_timestamp_utc
from golem.core.simpleserializer import CBORSerializer
from golem.network.p2p.node import Node
from golem.task import exceptions
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
            'mask': None,
            'fixed_header': {
                "task_id": idgenerator.generate_id(self.key_id),
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
                "subtasks_count": 21,
                "max_price": 10,
                "min_version": golem.__version__,
                "resource_size": 0,
                "estimated_memory": 0,
            }
        }

    def test_validate_ok(self):
        TaskHeader.validate(self.th_dict_repr)

    def test_validate_illegal_deadline(self):
        self.th_dict_repr['fixed_header']['deadline'] = datetime.now()
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Deadline is not a timestamp"
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_deadline_passed(self):
        self.th_dict_repr['fixed_header']['deadline'] = get_timestamp_utc() - 10
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Deadline already passed"
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_illegal_timeout(self):
        self.th_dict_repr['fixed_header']['subtask_timeout'] = "abc"
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Subtask timeout is not a number"
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_negative_timeout(self):
        self.th_dict_repr['fixed_header']['subtask_timeout'] = -131
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Subtask timeout is less than 0",
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_no_fixed_header(self):
        del self.th_dict_repr['fixed_header']
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Fixed header is missing"
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_no_task_id(self):
        del self.th_dict_repr['fixed_header']['task_id']
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Task ID missing",
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_no_task_owner(self):
        del self.th_dict_repr['fixed_header']['task_owner']
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "Task owner missing",
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_no_task_owner_node_name(self):
        del self.th_dict_repr['fixed_header']['task_owner']['node_name']
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            "node name missing",
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_no_subtasks_count(self):
        del self.th_dict_repr['fixed_header']['subtasks_count']
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            r"^Subtasks count is missing"
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_subtasks_count_invalid_type(self):
        self.th_dict_repr['fixed_header']['subtasks_count'] = None
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            r"^Subtasks count is missing",
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_validate_subtasks_count_too_low(self):
        self.th_dict_repr['fixed_header']['subtasks_count'] = -1
        with self.assertRaisesRegex(
            exceptions.TaskHeaderError,
            r"^Subtasks count is less than 1 {.*'subtasks_count': -1.*}$",
        ):
            TaskHeader.validate(self.th_dict_repr)

    def test_from_dict_no_subtasks_count(self):
        del self.th_dict_repr['fixed_header']['subtasks_count']
        with mock.patch("golem.task.taskbase.logger.debug") as log_mock:
            TaskHeader.from_dict(self.th_dict_repr)
            log_mock.assert_called_once()
