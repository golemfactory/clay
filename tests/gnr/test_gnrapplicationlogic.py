import unittest
import os

from gnr.gnrapplicationlogic import GNRApplicationLogic


class TestGNRApplicationLogic(unittest.TestCase):
    def test_root_path(self):
        logic = GNRApplicationLogic()
        self.assertTrue(os.path.isdir(logic.root_path))