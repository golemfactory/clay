import collections
import os
import sys
import hashlib
import appdirs
from calendar import timegm
from datetime import datetime
from multiprocessing import cpu_count

from queue import Queue, Empty

from twisted.internet.defer import Deferred, TimeoutError
from twisted.python.failure import Failure

import pytz

TIMEOUT_FORMAT = '{}:{:0=2d}:{:0=2d}'
DEVNULL = open(os.devnull, 'wb')
MAX_CPU_WINDOWS = 32
MAX_CPU_MACOS = 16


def get_local_datadir(name: str, root_dir=None) -> str:
    root_dir = os.path.join(appdirs.user_data_dir('golem'), name)
    return os.path.join(root_dir, "rinkeby")


def is_frozen():
    """
    Check if running a frozen script
    :return: True if executing a frozen script, False otherwise
    """
    return hasattr(sys, 'frozen') and sys.frozen


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


def is_linux():
    """
    Check if this system is Linux
    :return bool: True if current system is Linux, False otherwise
    """
    return sys.platform.startswith('linux')


def to_unicode(value):
    if value is None:
        return None
    try:
        if isinstance(value, bytes):
            return value.decode('utf-8')
        return str(value)
    except UnicodeDecodeError:
        return value


def update_dict(target, *updates):
    """
    Recursively update a dictionary
    :param target: dictionary to update
    :param updates: dictionaries to update with
    :return: updated target dictionary
    """
    for update in updates:
        for key, val in list(update.items()):
            if isinstance(val, collections.Mapping):
                target[key] = update_dict(target.get(key, {}), val)
            else:
                target[key] = update[key]
    return target


def get_golem_path():
    """
    Return path to main golem directory
    :return str: path to main golem directory
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


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
    return datetime_to_timestamp(now)


def timeout_to_deadline(timeout):
    return get_timestamp_utc() + timeout


def deadline_to_timeout(timestamp):
    return timestamp - get_timestamp_utc()


def timestamp_to_datetime(ts):
    return datetime.fromtimestamp(ts, pytz.utc)


def datetime_to_timestamp(then):
    return timegm(then.utctimetuple()) + then.microsecond / 1000000.0


def datetime_to_timestamp_utc(then):
    then_utc = then.astimezone(pytz.utc)
    return datetime_to_timestamp(then_utc)


def timeout_to_string(timeout):
    hours = int(timeout / 3600)
    timeout -= hours * 3600
    minutes = int(timeout / 60)
    timeout -= minutes * 60
    return TIMEOUT_FORMAT.format(hours, minutes, timeout)


def string_to_timeout(string):
    values = string.split(':')
    return int(values[0]) * 3600 + int(values[1]) * 60 + int(values[2])


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
        super(HandleKeyError, self).__init__(
            KeyError,
            handle_error
        )


class HandleAttributeError(HandleError):
    def __init__(self, handle_error):
        super(HandleAttributeError, self).__init__(
            AttributeError,
            handle_error
        )

def get_cpu_count():
    """
    Get number of cores with system limitations:
    - max 32 on Windows due to VBox limitation
    - max 16 on MacOS dut to xhyve limitation
    :return: number of cores
    """
    if is_windows():
        return min(cpu_count(), MAX_CPU_WINDOWS)  # VBox limitation
    if is_osx():
        return min(cpu_count(), MAX_CPU_MACOS)    # xhyve limitation
    return cpu_count()  # No limitatons on Linux

def sync_wait(deferred, timeout=10):
    if not isinstance(deferred, Deferred):
        return deferred

    queue = Queue()
    deferred.addBoth(queue.put)

    try:
        result = queue.get(True, timeout)
    except Empty:
        raise TimeoutError("Command timed out")

    if isinstance(result, Failure):
        result.raiseException()
    return result

def check_pow(proof, input_data, difficulty):
    """
    :param long proof:
    :param str input_data:
    :param int difficulty:
    :rtype bool:
    """
    sha = hashlib.sha256()
    sha.update(input_data.encode())
    sha.update(('%x' % proof).encode())
    h = int(sha.hexdigest()[0:8], 16)
    return h >= difficulty
