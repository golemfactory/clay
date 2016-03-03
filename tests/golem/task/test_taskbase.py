import unittest

from mock import Mock

from golem.task.taskbase import Task


class TestTaskBase(unittest.TestCase):
    def test_task(self):
        t = Task(Mock(), "")
        self.assertIsInstance(t, Task)
        self.assertEqual(t.get_stdout("abc"), "")
        self.assertEqual(t.get_stderr("abc"), "")
        self.assertEqual(t.get_results("abc"), [])
