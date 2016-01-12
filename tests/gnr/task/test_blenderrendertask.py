import unittest
import os

from gnr.task.blenderrendertask import BlenderDefaults


class TestBlenderDefaults(unittest.TestCase):
    def test_init(self):
        bd = BlenderDefaults()
        self.assertTrue(os.path.isfile(bd.main_program_file))
