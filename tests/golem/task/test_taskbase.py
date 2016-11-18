import json
import cbor2 as cbor

from mock import Mock

from golem.task.taskbase import Task, TaskHeader, TaskEventListener, logger
from golem.tools.assertlogs import LogTestCase
from golem.network.p2p.node import Node


class TestTaskBase(LogTestCase):

    def test_task(self):
        serializer = json
        self.__test(serializer=serializer)
        serializer = cbor
        self.__test(serializer=serializer)

    def __test(self, serializer):
        t = Task(Mock(), "")
        self.assertIsInstance(t, Task)
        self.assertEqual(t.get_stdout("abc"), "")
        self.assertEqual(t.get_stderr("abc"), "")
        self.assertEqual(t.get_results("abc"), [])

        t = Task(TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "key", "DEFAULT",
                            Node()), "print 'Hello world'")

        tl1 = TaskEventListener()
        tl2 = TaskEventListener()
        t.register_listener(tl1)
        t.register_listener(tl2)
        assert len(t.listeners) == 2
        p = serializer.dumps(t)
        u = serializer.loads(p)
        assert t.src_code == u.src_code
        assert t.header.task_id == u.header.task_id
        assert t.header.task_owner.node_name == u.header.task_owner.node_name
        assert u.get_results("abc") == []
        assert len(t.listeners) == 2
        assert len(u.listeners) == 0
        t.unregister_listener(tl2)
        assert len(t.listeners) == 1
        assert t.listeners[0] == tl1
        t.listeners[0].notify_update_task("abc")
        t.unregister_listener(tl1)
        assert len(t.listeners) == 0
        with self.assertLogs(logger, level="WARNING"):
            t.unregister_listener(tl1)
