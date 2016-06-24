import cPickle as pickle
import unittest

from mock import Mock

from golem.task.taskbase import Task, TaskHeader
from golem.network.p2p.node import Node


class TestTaskBase(unittest.TestCase):
    def test_task(self):
        t = Task(Mock(), "")
        self.assertIsInstance(t, Task)
        self.assertEqual(t.get_stdout("abc"), "")
        self.assertEqual(t.get_stderr("abc"), "")
        self.assertEqual(t.get_results("abc"), [])

        t = Task(TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "key", "DEFAULT",
                            Node()), "print 'Hello world'")

        p = pickle.dumps(t)
        u = pickle.loads(p)
        assert t.src_code == u.src_code
        assert t.header.task_id == u.header.task_id
        assert t.header.task_owner.node_name == u.header.task_owner.node_name
        assert u.get_results("abc") == []
