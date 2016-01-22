import sys
import os


def is_windows():
    """
    Check if this system is Windows
    :return bool: True if current system is Windows, False otherwise
    """
    return sys.platform == "win32"


def get_golem_path():
    """
    Return path to main golem directory
    :return str: path to diretory containing golem and gnr folder
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
