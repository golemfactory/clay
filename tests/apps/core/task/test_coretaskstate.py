from unittest import TestCase

from apps.core.task.coretaskstate import TaskDesc


class TestTaskDesc(TestCase):
    def test_init(self):
        td = TaskDesc()
        self.assertIsInstance(td, TaskDesc)
