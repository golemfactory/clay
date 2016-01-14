import unittest
import os

from gnr.task.vraytask import VrayDefaults


class TestVrayDefaults(unittest.TestCase):
    def test_init(self):
        vd = VrayDefaults()
        self.assertTrue(os.path.isfile(vd.main_program_file))
