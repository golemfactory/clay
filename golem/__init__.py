import pathlib
import subprocess
import sys

if sys.platform == "win32":
    # Sets the ShowWindow flag globally
    startupinfo = subprocess.STARTUPINFO
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

# PEP-396
try:
    with (pathlib.Path(__file__).parent / 'RELEASE-VERSION').open('r') as f:  # noqa pylint: disable=no-member
        __version__ = f.read()
except OSError:
    sys.stderr.write('Cannot determine version. Using default.\n')
    __version__ = '0.0.0'
