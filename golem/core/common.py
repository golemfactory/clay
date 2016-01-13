import sys


def is_windows():
    """
    Check if this system is Windows
    :return bool: True if current system is Windows, False otherwise
    """
    return sys.platform == "win32"
