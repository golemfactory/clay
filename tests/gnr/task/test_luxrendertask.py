import unittest
import os

from gnr.task.luxrendertask import LuxRenderDefaults


class TestLuxRenderDefaults(unittest.TestCase):
    def test_init(self):
        ld = LuxRenderDefaults()
        self.assertTrue(os.path.isfile(ld.main_program_file))
