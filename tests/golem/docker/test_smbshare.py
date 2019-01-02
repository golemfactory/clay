from pathlib import Path
from unittest import TestCase, skipUnless

from golem.core.common import is_windows
from golem.docker import smbshare


@skipUnless(is_windows(), 'Windows only')
class TestGetShareName(TestCase):

    DEFAULT_SHARE_NAME = "C37A161EDD52B4F2C7C59E6144A47595"

    def _assert_share_name(self, path, share_name=DEFAULT_SHARE_NAME):
        self.assertEqual(
            smbshare.get_share_name(Path(path)),
            share_name
        )

    def test_normal_path(self):
        self._assert_share_name(
            "C:\\Users\\golem\\AppData\\Local\\golem\\golem\\default\\"
            "rinkeby\\ComputerRes"
        )

    def test_trailing_backslash(self):
        self._assert_share_name(
            "C:\\Users\\golem\\AppData\\Local\\golem\\golem\\default\\"
            "rinkeby\\ComputerRes\\"
        )

    def test_slashes(self):
        self._assert_share_name(
            "C:/Users/golem/AppData/Local/golem/golem/default/"
            "rinkeby/ComputerRes"
        )

    def test_dots(self):
        self._assert_share_name(
            "C:\\Users\\golem\\AppData\\Local\\golem\\golem\\default\\"
            "rinkeby\\ComputerRes\\.\\tmp\\.."
        )

    def test_letter_case(self):
        self._assert_share_name(
            "c:\\USERS\\Golem\\appdata\\LOCAL\\GoLeM\\golem\\DEFAULT\\"
            "rinkeBY\\computerres"
        )
