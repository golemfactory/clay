import unittest
import os

from gnr.renderingdirmanager import get_task_scripts_path, find_task_script


class TestRenderingDirManager(unittest.TestCase):
    def test_get_task_scripts_path(self):
        self.assertTrue(os.path.isdir(get_task_scripts_path()))

    def find_task_script(self):
        path = find_task_script("bla")
        self.assertTrue(os.path.isdir(os.path.dirname(path)))
        self.assertEqual(os.path.basename(path), "bla")