import subprocess
import sys

if sys.platform == "win32":
    # Sets the ShowWindow flag globally
    startupinfo = subprocess.STARTUPINFO
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
