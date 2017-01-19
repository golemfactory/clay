import unittest

from golem.core.common import nt_path_to_posix_path


class TestNtPathToPosixPath(unittest.TestCase):

    def test_path_conversion(self):
        self.assertEqual(nt_path_to_posix_path("c:\\Users\\Golem"),
                         "/c/Users/Golem")
        self.assertEqual(nt_path_to_posix_path(u"c:\\Users\\Golem"),
                         "/c/Users/Golem")
        self.assertEqual(nt_path_to_posix_path("C:\\Program Files (x86)"),
                         "/c/Program Files (x86)")
        self.assertEqual(nt_path_to_posix_path("golem\\core\\common.py"),
                         "golem/core/common.py")
        self.assertEqual(nt_path_to_posix_path("C:\\"), "/c/")
        self.assertEqual(nt_path_to_posix_path("/var/lib"), "/var/lib")
        self.assertEqual(nt_path_to_posix_path(""), "")
