import os

from golem.core.common import is_osx


def fix_osx_tmpdir() -> bool:
    if not is_osx():
        return False
    tmpdir = os.environ.get('TMPDIR') or ''
    if not (tmpdir.startswith('/private') or tmpdir.startswith('/tmp')):
        os.environ['TMPDIR'] = '/tmp'
    return True
