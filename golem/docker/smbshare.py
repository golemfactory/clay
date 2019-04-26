import binascii
import hashlib
from os import path, makedirs
from pathlib import Path
import sys

from golem.core.common import get_golem_path, is_windows
from golem.core.windows import run_powershell

SCRIPT_PATH = path.join(
    get_golem_path(), 'scripts', 'docker', 'create-share.ps1')
SCRIPT_TIMEOUT = 180  # seconds


def create_share(user_name: str, shared_dir_path: Path) -> None:
    if not is_windows():
        raise OSError

    if not shared_dir_path.is_dir():
        makedirs(shared_dir_path, exist_ok=True)

    run_powershell(
        script=SCRIPT_PATH,
        timeout=SCRIPT_TIMEOUT,
        args=['-UserName', user_name, '-SharedDirPath', str(shared_dir_path)],
    )


def get_share_name(shared_dir_path: Path) -> str:
    import win32file  # pylint: disable=import-error

    if not shared_dir_path.is_dir():
        raise ValueError(f"There's no such directory as '{shared_dir_path}'")

    # normalize -> encode -> MD5 digest -> hexlify -> decode -> uppercase
    norm_path: str = path.normpath(shared_dir_path)  # type: ignore
    norm_path = win32file.GetLongPathName(norm_path)
    norm_path = path.normcase(norm_path)
    return binascii.hexlify(
        hashlib.md5(
            norm_path.encode()
        ).digest()
    ).decode().upper()


if __name__ == '__main__':
    create_share(sys.argv[1], Path(sys.argv[2]))
