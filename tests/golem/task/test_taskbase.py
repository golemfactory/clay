from mock import Mock

from golem.core.simpleserializer import CBORSerializer, SimpleSerializer
from golem.docker.image import DockerImage
from golem.network.p2p.node import Node
from golem.task.taskbase import Task, TaskHeader, TaskEventListener, logger
from golem.tools.assertlogs import LogTestCase


class TestTaskBase(LogTestCase):

    def test_task_simple_serializer(self):
        with self.assertRaises(TypeError):
            Task.build_task("Not Task Builder")
        with self.assertRaises(TypeError):
            Task.register_listener("Not Listener")
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
        p = SimpleSerializer.dumps(t)
        u = SimpleSerializer.loads(p)
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

    def test_header_serialization(self):
        node = dict(node_name="test node")
        docker_images = [
            dict(
                repository="repo_{}".format(i),
                id="id_{}".format(i),
                tag="tag_{}".format(i)
            )
            for i in xrange(4)
        ]

        task_header = TaskHeader("ABC", "xyz", "10.10.10.10", 1023, "key", "DEFAULT",
                                 task_owner=node, docker_images=docker_images)
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
        assert all([isinstance(di, DockerImage) for di in task_header_from_dict.docker_images])

        task_header_bin = task_header.to_binary()
        bin_serialized = CBORSerializer.dumps(task_header_bin)
        bin_deserialized = CBORSerializer.loads(bin_serialized)

        assert bin_deserialized == task_header_bin
