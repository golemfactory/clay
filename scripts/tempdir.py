import os
import re

from golem.core.common import is_osx


def fix_osx_tmpdir() -> bool:
    if not is_osx():
        return False
    tmpdir = os.environ.get('TMPDIR') or ''
    if not re.match('^/(private|tmp|Users|Volumes).*', tmpdir):
        os.environ['TMPDIR'] = '/tmp'
        print(
            f"\033[0;31m"
            f"TMPDIR updated to something that Docker can mount: "
            f"{os.environ.get('TMPDIR')}"
            f"\033[0m"
        )
        return True
    return False
