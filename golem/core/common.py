import collections
import logging.config
import os
import subprocess
import sys
from calendar import timegm
from datetime import datetime
from functools import wraps
from typing import Any, Callable, cast, List, TypeVar

import pytz

from golem.core import simpleenv

F = TypeVar('F', bound=Callable[..., Any])

TIMEOUT_FORMAT = '{}:{:0=2d}:{:0=2d}'
DEVNULL = open(os.devnull, 'wb')


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


def posix_path(path):
    if is_windows():
        return nt_path_to_posix_path(path)
    return path


def unix_pipe(source_cmd: List[str], sink_cmd: List[str]) -> str:
    source = subprocess.Popen(source_cmd,
                              stdout=subprocess.PIPE)
    sink = subprocess.Popen(sink_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdin=source.stdout)
    source.stdout.close()
    stdout, _ = sink.communicate()
    return stdout.strip()


def get_timestamp_utc():
    now = datetime.now(pytz.utc)
    return datetime_to_timestamp(now)


def timeout_to_deadline(timeout) -> int:
    return int(get_timestamp_utc() + timeout)


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


def string_to_timeout(string: str) -> int:
    values = string.split(':')
    return int(values[0]) * 3600 + int(values[1]) * 60 + int(values[2])


def node_info_str(name, node_id):
    short_id = short_node_id(node_id)
    return f"'{name}'({short_id})"


def short_node_id(node_id):
    return f'{node_id[:8]}..{node_id[-8:]}'


class HandleError(object):
    def __init__(self, error, handle_error):
        self.handle_error = handle_error
        self.error = error

    def __call__(self, func: F) -> F:
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except self.error:
                return self.handle_error(*args, **kwargs)

        return cast(F, func_wrapper)


class HandleForwardedError:
    def __init__(self, error, handle_error):
        self.handle_error = handle_error
        self.error = error

    def __call__(self, func: F) -> F:
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except self.error as err:
                return self.handle_error(err)

        return cast(F, func_wrapper)


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


def retry(exc_cls, count: int):
    assert exc_cls, "Class not provided"
    assert count >= 0, "Invalid retry count"

    if not isinstance(exc_cls, (list, tuple)):
        exc_cls = (exc_cls,)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for _ in range(count + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    last_exc = exc
                    if not isinstance(exc, exc_cls):
                        break
            # pylint: disable=raising-bad-type
            raise last_exc
        return wrapper
    return decorator


def config_logging(suffix='', datadir=None, loglevel=None, config_desc=None):
    """Config logger"""
    try:
        from loggingconfig_local import LOGGING
    except ImportError:
        from loggingconfig import LOGGING

    if datadir is None:
        datadir = simpleenv.get_local_datadir("default")
    logdir_path = os.path.join(datadir, 'logs')

    for handler_name, handler in LOGGING.get('handlers', {}).items():
        if 'filename' in handler:
            handler['filename'] %= {
                'logdir': str(logdir_path),
                'suffix': suffix,
            }
        skip_handler_names = (
            'error-file',
            'sentry',
            'sentry-metrics',
        )
        if handler_name in skip_handler_names:
            # Don't modify loglevel in this handler
            continue
        if loglevel:
            handler['level'] = loglevel

    if loglevel:
        for _logger in LOGGING.get('loggers', {}).values():
            _logger['level'] = loglevel
        LOGGING['root']['level'] = loglevel
        if config_desc and not config_desc.debug_third_party:
            LOGGING['loggers']['golem.rpc.crossbar']['level'] = 'WARNING'
            LOGGING['loggers']['twisted']['level'] = 'WARNING'

    try:
        if not os.path.exists(logdir_path):
            os.makedirs(logdir_path)

        logging.config.dictConfig(LOGGING)
    except (ValueError, PermissionError) as e:
        sys.stderr.write(
            "Can't configure logging in: {} Got: {}\n".format(logdir_path, e)
        )
        return  # Avoid consequent errors
    logging.captureWarnings(True)

    from golem.tools.talkback import enable_sentry_logger
    enable_sentry_logger(False)
    import txaio
    txaio.use_twisted()
    from ethereum import slogging
    if config_desc and config_desc.debug_third_party:
        slogging.configure(':debug')
    else:
        slogging.configure(':warning')

    from twisted.python import log
    observer = log.PythonLoggingObserver(loggerName='twisted')
    observer.start()

    crossbar_log_lvl = logging.getLevelName(
        logging.getLogger('golem.rpc.crossbar').level).lower()
    # Fix inconsistency in log levels, only warn affected
    if crossbar_log_lvl == 'warning':
        crossbar_log_lvl = 'warn'

    txaio.set_global_log_level(crossbar_log_lvl)  # pylint: disable=no-member


def install_reactor():

    if is_windows():
        from twisted.internet import iocpreactor
        iocpreactor.install()
    elif is_osx():
        from twisted.internet import kqreactor
        kqreactor.install()

    from twisted.internet import reactor
    from golem.core.variables import REACTOR_THREAD_POOL_SIZE
    reactor.suggestThreadPoolSize(REACTOR_THREAD_POOL_SIZE)
    return reactor


if is_windows():
    SUBPROCESS_STARTUP_INFO = subprocess.STARTUPINFO()
    SUBPROCESS_STARTUP_INFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    SUBPROCESS_STARTUP_INFO = None
