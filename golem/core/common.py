import sys
import os
from datetime import datetime, timedelta


def is_windows():
    """
    Check if this system is Windows
    :return bool: True if current system is Windows, False otherwise
    """
    return sys.platform == "win32"


def is_osx():
    """
    Check if this system is OS X
    :return bool: True if current system is OS X, False otherwise
    """
    return sys.platform == "darwin"


def get_golem_path():
    """
    Return path to main golem directory
    :return str: path to diretory containing golem and gnr folder
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def nt_path_to_posix_path(path):
    """Replaces all "\"'s in a specified path by "/"'s and replaces
    the leading "X:" (driver letter), if present, with "/x".
    :param str path:
    :return str:
    """
    path = path.replace("\\", "/")
    parts = path.split(":")
    if len(parts) > 1:
        return "/" + parts[0].lower() + parts[1]
    return path


def deadline_to_timeout(deadline):
    """ Return number of seconds from now to deadline
    :param datetime deadline: UTC datetime
    :return float:
    """
    return (deadline - datetime.utcnow()).total_seconds()


def timeout_to_deadline(timeout):
    """ Return utctime <timeout> seconds from now
    :param float timeout:
    :return datetime:
    """
    return datetime.utcnow() + timedelta(seconds=timeout)


class HandleKeyError(object):
    def __init__(self, handle_error):
        self.handle_error = handle_error

    def __call__(self, func):
        def func_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except KeyError:
                return self.handle_error(*args, **kwargs)
        return func_wrapper

