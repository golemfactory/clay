import os
import errno
import sys
from datetime import datetime, timedelta
from os import path

import pytz


LOG_NAME = "golem.log"


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


def get_current_time():
    return datetime.now(pytz.utc)


def deadline_to_timeout(deadline):
    """ Return number of seconds from now to deadline
    :param datetime deadline: UTC datetime
    :return float:
    """
    return (deadline - get_current_time()).total_seconds()


def timeout_to_deadline(timeout):
    """ Return utctime <timeout> seconds from now
    :param float timeout:
    :return datetime:
    """
    return get_current_time() + timedelta(seconds=timeout)


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

    # \t and other special chars cause problems with log handlers
    logname = logname.encode('string-escape')
    directory = os.path.dirname(logname)

    if directory:
        try:
            os.makedirs(directory)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

    import logging.config
    config_file = path.normpath(path.join(get_golem_path(), "gnr", "logging.ini"))
    logging.config.fileConfig(config_file, defaults={'logname': logname}, disable_existing_loggers=False)

