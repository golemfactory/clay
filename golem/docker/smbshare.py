from os import path
import subprocess
from subprocess import CalledProcessError, TimeoutExpired
import sys

from golem.core.common import get_golem_path, is_windows

SCRIPT_PATH = path.join(get_golem_path(), 'scripts', 'create-share.ps1')
SCRIPT_TIMEOUT = 60  # seconds


def create_share(user_name: str, shared_dir_path: str) -> None:
    if not is_windows():
        raise OSError

    try:
        subprocess.run(
            [
                'powershell.exe',
                '-File', SCRIPT_PATH,
                '-UserName', user_name,
                '-SharedDirPath', shared_dir_path
            ],
            timeout=SCRIPT_TIMEOUT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
    except (CalledProcessError, TimeoutExpired) as exc:
        raise RuntimeError(exc.stdout.decode('utf8'))


if __name__ == '__main__':
    create_share(sys.argv[1], sys.argv[2])
