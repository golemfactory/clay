from calendar import timegm
import collections
from datetime import datetime
import logging.config
from multiprocessing import cpu_count
import os
import sys
import pytz

from golem.core import simpleenv
from golem.core.variables import REACTOR_THREAD_POOL_SIZE

TIMEOUT_FORMAT = '{}:{:0=2d}:{:0=2d}'
DEVNULL = open(os.devnull, 'wb')
MAX_CPU_WINDOWS = 32
MAX_CPU_MACOS = 16

ALLOWED_LOGLEVELS = [
    'ERROR'
    'WARNING',
    'INFO',
    'DEBUG'
]


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


def config_logging(suffix='', datadir=None, loglevel=None):
    """Config logger"""
    try:
        from loggingconfig_local import LOGGING
    except ImportError:
        from loggingconfig import LOGGING

    if datadir is None:
        datadir = simpleenv.get_local_datadir("default")
    logdir_path = os.path.join(datadir, 'logs')

    wrong_loglevel = None
    if loglevel and loglevel not in ALLOWED_LOGLEVELS:
        wrong_loglevel = loglevel
        loglevel = None

    for handler in LOGGING.get('handlers', {}).values():
        if loglevel:
            handler['level'] = loglevel
        if 'filename' in handler:
            handler['filename'] %= {
                'logdir': str(logdir_path),
                'suffix': suffix,
            }

    if loglevel:
        for _logger in LOGGING.get('loggers', {}).values():
            if 'level' in _logger:
                _logger['level'] = loglevel
        LOGGING['root']['level'] = loglevel

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

    logger = logging.getLogger(__name__)
    if wrong_loglevel is not None:
        logger.warning('Invalid log level "%r", reset to default.',
                       wrong_loglevel)

    import txaio
    txaio.use_twisted()
    from ethereum import slogging
    slogging.configure(':debug')
    from twisted.python import log
    observer = log.PythonLoggingObserver(loggerName='twisted')
    observer.start()

    crossbar_log_lvl = logging.getLevelName(
        logging.getLogger('golem.rpc.crossbar').level).lower()
    # Fix inconsistency in log levels, only warn affected
    if crossbar_log_lvl == 'warning':
        crossbar_log_lvl = 'warn'

    txaio.set_global_log_level(crossbar_log_lvl)  # pylint: disable=no-member


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


def install_reactor():

    if is_windows():
        from twisted.internet import iocpreactor
        iocpreactor.install()
    elif is_osx():
        from twisted.internet import kqreactor
        kqreactor.install()

    from twisted.internet import reactor
    reactor.suggestThreadPoolSize(REACTOR_THREAD_POOL_SIZE)
    return reactor
