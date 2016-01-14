import unittest
import os

from gnr.renderingdirmanager import get_task_scripts_path, get_benchmarks_path


class TestRenderingDirManager(unittest.TestCase):
    def test_get_tasks_scripts_path(self):
        self.assertTrue(os.path.isdir(get_task_scripts_path()))

    def test_get_benchmarks_path(self):
        self.assertTrue(os.path.isdir(get_benchmarks_path()))
