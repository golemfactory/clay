from mock import Mock

from golem.tools.assertlogs import LogTestCase
from golem.task.tasksession import TaskSession, logger

class TestTaskSession(LogTestCase):
    def test_init(self):
        ts = TaskSession(Mock())
        self.assertIsInstance(ts, TaskSession)

    def test_encrypt(self):
        ts = TaskSession(Mock())
        data = "ABC"

        ts.key_id = "123"
        res = ts.encrypt(data)
        ts.task_server.encrypt.assert_called_with(data, "123")

        ts.task_server = None
        with self.assertLogs(logger, level=1):
            self.assertEqual(ts.encrypt(data), data)

    def test_decrypt(self):
        ts = TaskSession(Mock())
        data = "ABC"

        res = ts.decrypt(data)
        ts.task_server.decrypt.assert_called_with(data)
        self.assertIsNotNone(res)

        ts.task_server.decrypt = Mock(side_effect=AssertionError("Encrypt error"))
        with self.assertLogs(logger, level=1) as l:
            res = ts.decrypt(data)
        self.assertTrue(any(["maybe it's not encrypted?" in log for log in l.output]))
        self.assertFalse(any(["Encrypt error" in log for log in l.output]))
        self.assertEqual(res, data)

        ts.task_server.decrypt = Mock(side_effect=ValueError("Different error"))
        with self.assertLogs(logger, level=1) as l:
            res = ts.decrypt(data)
        self.assertTrue(any(["Different error" in log for log in l.output]))
        self.assertIsNone(res)

        ts.task_server = None
        data = "ABC"
        with self.assertLogs(logger, level=1):
            self.assertEqual(ts.encrypt(data), data)

