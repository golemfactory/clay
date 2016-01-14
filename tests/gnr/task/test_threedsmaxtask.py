import unittest
import os

from gnr.task.threedsmaxtask import ThreeDSMaxDefaults


class TestThreeDSMaxDefaults(unittest.TestCase):
    def test_init(self):
        td = ThreeDSMaxDefaults()
        self.assertTrue(os.path.isfile(td.main_program_file))
