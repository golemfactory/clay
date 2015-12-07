import unittest
import os
from golem.environments.utils import find_program


class TestCheckCmd(unittest.TestCase):
    def test_find_program(self):
        self.assertTrue(find_program('python'))
        self.assertFalse(find_program('afjaljl'))

        if os.name == 'nt':
            cmd = find_program('cmd')
            assert cmd.lower().endswith('cmd.exe')
