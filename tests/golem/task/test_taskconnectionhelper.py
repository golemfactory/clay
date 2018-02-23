import time
import unittest
import unittest.mock as mock
import uuid

from golem.task.taskconnectionshelper import TaskConnectionsHelper


class MockNodeInfo(object):

    def __init__(self):
        self.key = str(uuid.uuid4())


class TestTaskConnectionsHelper(unittest.TestCase):
    def test_init(self):
        tch = TaskConnectionsHelper()
        self.assertIsInstance(tch, TaskConnectionsHelper)

    def test_is_new_conn_request(self):
        nodeinfo = MockNodeInfo()
        nodeinfo1 = MockNodeInfo()
        nodeinfo3 = MockNodeInfo()
        tch = TaskConnectionsHelper()

        self.assertTrue(tch.is_new_conn_request("ABC", nodeinfo))
        self.assertFalse(tch.is_new_conn_request("ABC", nodeinfo))

        timestamp = tch.conn_to_set.get(("ABC", nodeinfo.key))
        self.assertLessEqual(timestamp, time.time())

        self.assertTrue(tch.is_new_conn_request("DEF", nodeinfo1))

        timestamp = tch.conn_to_set.get(("ABC", nodeinfo.key))
        self.assertLessEqual(timestamp, time.time())

        self.assertTrue(tch.is_new_conn_request("DEF", nodeinfo3))

    def test_want_to_start(self):
        nodeinfo = MockNodeInfo()
        nodeinfo2 = MockNodeInfo()
        tch = TaskConnectionsHelper()
        tch.task_server = mock.MagicMock()
        self.assertIsNone(tch.conn_to_start.get("abc"))
        tch.want_to_start("abc", nodeinfo, "supernodeinfo")
        data = tch.conn_to_start.get("abc")
        self.assertEqual(data[0], nodeinfo)
        self.assertEqual(data[1], "supernodeinfo")
        self.assertLessEqual(data[2], time.time())
        tch.task_server.start_task_session.assert_called_once_with(nodeinfo, "supernodeinfo", "abc")
        tch.want_to_start("abc", nodeinfo2, "supernodeinfo2")
        tch.task_server.start_task_session.assert_called_once_with(nodeinfo, "supernodeinfo", "abc")
        tch.want_to_start("abc", nodeinfo, "supernodeinfo")
        tch.task_server.start_task_session.assert_called_once_with(nodeinfo, "supernodeinfo", "abc")

    def test_sync(self):
        nodeinfo = MockNodeInfo()
        nodeinfo1 = MockNodeInfo()
        nodeinfo2 = MockNodeInfo()
        tch = TaskConnectionsHelper()
        tch.task_server = mock.MagicMock()
        tch.remove_old_interval = 1
        tch.sync()
        self.assertEqual(len(tch.conn_to_set), 0)
        self.assertEqual(len(tch.conn_to_start), 0)
        tch.want_to_start("abc", nodeinfo, "supernodeinfo")
        tch.want_to_start("def", nodeinfo1, "supernodeinfo1")
        tch.is_new_conn_request("ABCK", nodeinfo)
        tch.is_new_conn_request("DEFK", nodeinfo1)
        time.sleep(2)
        tch.want_to_start("ghi", nodeinfo1, "supernodeinfo1")
        tch.is_new_conn_request("GHIK", nodeinfo2)
        self.assertEqual(len(tch.conn_to_start), 3)
        self.assertEqual(len(tch.conn_to_set), 3)
        tch.sync()
        self.assertEqual(len(tch.conn_to_start), 1)
        self.assertEqual(len(tch.conn_to_set), 1)
        data = tch.conn_to_start["ghi"]
        self.assertEqual(data[0], nodeinfo1)
        self.assertEqual(data[1], "supernodeinfo1")
        self.assertLessEqual(data[2], time.time())
        timestamp = tch.conn_to_set[("GHIK", nodeinfo2.key)]
        self.assertLessEqual(timestamp, time.time())
        time.sleep(1.5)
        tch.sync()
        self.assertEqual(len(tch.conn_to_start), 0)
        # self.assertEqual(len(tch.conn_to_set), 0)
