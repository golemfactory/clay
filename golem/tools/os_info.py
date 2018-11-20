import platform as platform_lib
import sys
from typing import Optional, Tuple

import distro

from golem.core.common import is_windows, is_linux


class OSInfo:

    WIN_VERSION_KEY = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    WIN_EDITION_ID = 'EditionID'

    # pylint: disable=too-many-arguments
    def __init__(
            self,
            platform: str,
            system: str,
            release: str,
            version: str,
            windows_edition: Optional[str] = None,
            linux_distribution: Optional[Tuple[str, str, str]] = None,
    ) -> None:
        self.platform = platform
        self.system = system
        self.release = release
        self.version = version
        self.windows_edition = windows_edition
        # Linux distribution is a triplet: (distribution, version, codename)
        # E.g. ('Ubuntu', '16.04', 'Xenial Xerus')
        self.linux_distribution = linux_distribution

    @classmethod
    def get_os_info(cls) -> 'OSInfo':
        return cls(
            platform=sys.platform,
            system=platform_lib.system(),
            release=platform_lib.release(),
            version=platform_lib.version(),
            windows_edition=cls._get_windows_edition(),
            linux_distribution=cls._get_linux_distribution()
        )

    @classmethod
    def _get_windows_edition(cls) -> Optional[str]:
        if not is_windows():
            return None

        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls.WIN_VERSION_KEY)
            return winreg.QueryValueEx(key, cls.WIN_EDITION_ID)[0]
        except (ImportError, FileNotFoundError, KeyError):
            return None

    @classmethod
    def _get_linux_distribution(cls) -> Optional[Tuple[str, str, str]]:
        if not is_linux():
            return None

        return distro.linux_distribution()
