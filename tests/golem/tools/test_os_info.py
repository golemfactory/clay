from unittest import TestCase, skipIf

from golem.core.common import is_windows, is_linux, is_osx
from golem.tools.os_info import OSInfo


class TestOSInfo(TestCase):

    @skipIf(not is_windows(), 'Windows only')
    def test_get_os_info_windows(self):
        os_info = OSInfo.get_os_info()
        self.assertEqual(os_info.platform, 'win32')
        self.assertEqual(os_info.system, 'Windows')
        self.assertIsNotNone(os_info.release)
        self.assertIsNotNone(os_info.version)
        self.assertIsNotNone(os_info.windows_edition)
        self.assertIsNone(os_info.linux_distribution)

    @skipIf(not is_linux(), 'Linux only')
    def test_get_os_info_linux(self):
        os_info = OSInfo.get_os_info()
        self.assertEqual(os_info.platform, 'linux')
        self.assertEqual(os_info.system, 'Linux')
        self.assertIsNotNone(os_info.release)
        self.assertIsNotNone(os_info.version)
        self.assertIsNotNone(os_info.linux_distribution)
        self.assertIsNone(os_info.windows_edition)

    @skipIf(not is_osx(), 'macOS only')
    def test_get_os_info_macos(self):
        os_info = OSInfo.get_os_info()
        self.assertEqual(os_info.platform, 'darwin')
        self.assertEqual(os_info.system, 'Darwin')
        self.assertIsNotNone(os_info.release)
        self.assertIsNotNone(os_info.version)
        self.assertIsNone(os_info.linux_distribution)
        self.assertIsNone(os_info.windows_edition)
