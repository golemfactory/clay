import unittest
import time

from mock import MagicMock

from golem.task.taskconnectionshelper import TaskConnectionsHelper


class MockNodeInfo(object):
    pass


class TestTaskConnectionsHelper(unittest.TestCase):
    def test_init(self):
        tch = TaskConnectionsHelper()
        self.assertIsInstance(tch, TaskConnectionsHelper)

    def test_is_new_conn_request(self):
        nodeinfo = MockNodeInfo()
        nodeinfo1 = MockNodeInfo()
        nodeinfo3 = MockNodeInfo()
        tch = TaskConnectionsHelper()
        self.assertTrue(tch.is_new_conn_request("abc", "ABC", nodeinfo, "supernodeinfo"))
        self.assertTrue(tch.is_new_conn_request("def", "ABC", nodeinfo, "supernodeinfo"))
        self.assertFalse(tch.is_new_conn_request("abc", "ABC", nodeinfo, "supernodeinfo"))
        self.assertFalse(tch.is_new_conn_request("abc", "DEF", nodeinfo1, "supernodeinfo2"))
        self.assertFalse(tch.is_new_conn_request("def", "DEF", nodeinfo3, "supernodeinfo3"))
        data = tch.conn_to_set.get("abc")
        self.assertEqual(data[0], "ABC")
        self.assertEqual(data[1](), nodeinfo)
        self.assertEqual(data[2], "supernodeinfo")
        self.assertLessEqual(data[3], time.time())
        data = tch.conn_to_set.get("def")
        self.assertEqual(data[0], "ABC")
        self.assertEqual(data[1](), nodeinfo)
        self.assertEqual(data[2], "supernodeinfo")
        self.assertLessEqual(data[3], time.time())

    def test_want_to_start(self):
        nodeinfo = MockNodeInfo()
        nodeinfo2 = MockNodeInfo()
        tch = TaskConnectionsHelper()
        tch.task_server = MagicMock()
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
        tch.task_server = MagicMock()
        tch.remove_old_interval = 1
        tch.sync()
        self.assertEqual(len(tch.conn_to_set), 0)
        self.assertEqual(len(tch.conn_to_start), 0)
        tch.want_to_start("abc", nodeinfo, "supernodeinfo")
        tch.want_to_start("def", nodeinfo1, "supernodeinfo1")
        tch.is_new_conn_request("ABC", "ABCK", nodeinfo, "supernodeinfo")
        tch.is_new_conn_request("DEF", "DEFK", nodeinfo1, "supernodeinfo1")
        time.sleep(2)
        tch.want_to_start("ghi", nodeinfo1, "supernodeinfo1")
        tch.is_new_conn_request("GHI", "GHIK", nodeinfo2, "supernodeinfo2")
        self.assertEqual(len(tch.conn_to_start), 3)
        self.assertEqual(len(tch.conn_to_set), 3)
        tch.sync()
        self.assertEqual(len(tch.conn_to_start), 1)
        self.assertEqual(len(tch.conn_to_set), 1)
        data = tch.conn_to_start["ghi"]
        self.assertEqual(data[0], nodeinfo1)
        self.assertEqual(data[1], "supernodeinfo1")
        self.assertLessEqual(data[2], time.time())
        data = tch.conn_to_set["GHI"]
        self.assertEqual(data[0], "GHIK")
        self.assertEqual(data[1](), nodeinfo2)
        self.assertEqual(data[2], "supernodeinfo2")
        self.assertLessEqual(data[3], time.time())
        time.sleep(1.5)
        tch.sync()
        self.assertEqual(len(tch.conn_to_start), 0)
        # self.assertEqual(len(tch.conn_to_set), 0)

