import unittest
from golem.environments.checkcmd import check_cmd


class TestCheckCmd(unittest.TestCase):
    def testCheckCmd(self):
        self.assertTrue(check_cmd('python'))
        self.assertTrue(check_cmd('python', no_output=False))
        self.assertFalse(check_cmd('afjaljl'))
        self.assertFalse(check_cmd('wkeajkajf', no_output=False))
