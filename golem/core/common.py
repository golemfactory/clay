import os
import sys
from os import path

LOG_NAME = "golem.log"

ETH = 1 / float(10**18)


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


def config_logging(logname=LOG_NAME):
    """Config logger"""
    import logging.config
    config_file = path.normpath(path.join(get_golem_path(), "gnr", "logging.ini"))
    logging.config.fileConfig(config_file, defaults={'logname': logname}, disable_existing_loggers=False)
