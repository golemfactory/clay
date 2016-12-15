from unittest import TestCase

from apps.core.task.gnrtaskstate import TaskDesc


class TestTaskDesc(TestCase):
    def test_init(self):
        td = TaskDesc()
        self.assertIsInstance(td, TaskDesc)
