import unittest
import os

from gnr.task.pbrtgnrtask import PbrtDefaults


class TestPbrtDefaults(unittest.TestCase):
    def test_init(self):
        pd = PbrtDefaults()
        self.assertTrue(os.path.isfile(pd.main_program_file))
