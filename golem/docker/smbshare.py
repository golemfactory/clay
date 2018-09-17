import binascii
import hashlib
from os import path, makedirs
import subprocess
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired
import sys

from golem.core.common import get_golem_path, is_windows

SCRIPT_PATH = path.join(get_golem_path(), 'scripts', 'create-share.ps1')
SCRIPT_TIMEOUT = 60  # seconds


def create_share(user_name: str, shared_dir_path: Path) -> None:
    if not is_windows():
        raise OSError

    if not shared_dir_path.is_dir():
        makedirs(shared_dir_path, exist_ok=True)
    try:
        subprocess.run(
            [
                'powershell.exe',
                '-File', SCRIPT_PATH,
                '-UserName', user_name,
                '-SharedDirPath', str(shared_dir_path)
            ],
            timeout=SCRIPT_TIMEOUT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
    except (CalledProcessError, TimeoutExpired) as exc:
        raise RuntimeError(exc.stdout.decode('utf8'))


def get_share_name(shared_dir_path: Path) -> str:
    # normalize -> encode -> MD5 digest -> hexlify -> decode -> uppercase
    norm_path = path.normcase(shared_dir_path.absolute())
    return binascii.hexlify(
        hashlib.md5(
            norm_path.encode()
        ).digest()
    ).decode().upper()


if __name__ == '__main__':
    create_share(sys.argv[1], Path(sys.argv[2]))
