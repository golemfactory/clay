import os
import errno
import sys
from calendar import timegm
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


def get_timestamp_utc():
    now = datetime.now(pytz.utc)
    return timegm(now.utctimetuple()) + now.microsecond / 1000000.0


def timeout_to_deadline(timeout):
    return get_timestamp_utc() + timeout


def deadline_to_timeout(timestamp):
    return timestamp - get_timestamp_utc()


def timestamp_to_datetime(ts):
    return datetime.fromtimestamp(ts, pytz.utc)


class HandleError(object):
    def __init__(self, error, handle_error):
        self.handle_error = handle_error
        self.error = error

    def __call__(self, func):
        def func_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except self.error:
                return self.handle_error(*args, **kwargs)
        return func_wrapper


class HandleKeyError(HandleError):
    def __init__(self, handle_error):
        super(HandleKeyError, self).__init__(KeyError, handle_error)


class HandleAttributeError(HandleError):
    def __init__(self, handle_error):
        super(HandleAttributeError, self).__init__(AttributeError, handle_error)


def config_logging(logname=LOG_NAME):
    """Config logger"""

    # \t and other special chars cause problems with log handlers
    if isinstance(logname, unicode):
        escaping = 'unicode-escape'
    else:
        escaping = 'string-escape'

    logname = logname.encode(escaping)
    directory = os.path.dirname(logname)

    if directory:
        try:
            os.makedirs(directory)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

    import logging.config
    config_file = path.normpath(path.join(get_golem_path(), "logging.ini"))
    logging.config.fileConfig(config_file, defaults={'logname': logname}, disable_existing_loggers=False)

