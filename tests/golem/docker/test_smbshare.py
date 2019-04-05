import os
import shutil
from pathlib import Path
from unittest import TestCase, skipUnless

from golem.core.common import is_windows
from golem.docker import smbshare


@skipUnless(is_windows(), 'Windows only')
class TestGetShareName(TestCase):

    DEFAULT_SHARE_PATH = "C:\\Users\\Public\\AppData\\Local\\golem\\golem\\" \
                         "default\\rinkeby\\ComputerRes"
    DEFAULT_SHARE_NAME = "C97956C9B0D048CCC69B36413DBC994E"

    @classmethod
    def setUpClass(cls):
        # The path must exist for get_share_name() to work correctly.
        # We cannot use a temp directory because it does not have a fixed path
        # and, in turn, a fixed share name.
        # In the cleanup we want to remove only what we created.
        current_path = Path("C:\\")
        for dirname in cls.DEFAULT_SHARE_PATH.split('\\')[1:]:
            current_path /= dirname
            if not current_path.is_dir():
                cls._path_to_remove = current_path
                break
        else:
            cls._path_to_remove = None

        os.makedirs(cls.DEFAULT_SHARE_PATH, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._path_to_remove)

    def _assert_share_name(self, path, share_name=DEFAULT_SHARE_NAME):
        self.assertEqual(
            smbshare.get_share_name(Path(path)),
            share_name
        )

    def test_normal_path(self):
        self._assert_share_name(self.DEFAULT_SHARE_PATH)

    def test_trailing_backslash(self):
        self._assert_share_name(
            "C:\\Users\\Public\\AppData\\Local\\golem\\golem\\default\\"
            "rinkeby\\ComputerRes\\"
        )

    def test_slashes(self):
        self._assert_share_name(
            "C:/Users/Public/AppData/Local/golem/golem/default/"
            "rinkeby/ComputerRes"
        )

    def test_dots(self):
        self._assert_share_name(
            "C:\\Users\\Public\\AppData\\Local\\golem\\golem\\default\\"
            "rinkeby\\ComputerRes\\.\\tmp\\.."
        )

    def test_letter_case(self):
        self._assert_share_name(
            "c:\\USERS\\puBlic\\appdata\\LOCAL\\GoLeM\\golem\\DEFAULT\\"
            "rinkeBY\\computerres"
        )

    def test_shortened_path(self):
        self._assert_share_name(
            "C:\\Users\\Public\\AppData\\Local\\golem\\golem\\default\\"
            "rinkeby\\COMPUT~1"
        )
