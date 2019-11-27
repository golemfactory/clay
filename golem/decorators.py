import datetime
import functools
import itertools
import logging


log = logging.getLogger('golem.decorators')


def run_with_db():
    """Run only when DB is active"""
    from golem import model

    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            if model.db.is_closed():
                log.debug(
                    '%s.%s disabled. DB inactive',
                    f.__module__,
                    f.__qualname__,
                )
                return None
            return f(*args, **kwargs)
        return curry
    return wrapped


def locked(lock):
    """Run under a threadsafe lock"""
    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            with lock:
                return f(*args, **kwargs)
        return curry
    return wrapped


def surge_detector(timeout: datetime.timedelta, treshold: int):
    """Log when surge of calls is detected"""
    def wrapped(f):
        deadline = datetime.datetime.now()
        count = itertools.count()
        calls_counters = {}

        def _reset():
            nonlocal deadline
            nonlocal count
            nonlocal calls_counters
            deadline = datetime.datetime.now() + timeout
            count = itertools.count()
            calls_counters = {}
        _reset()

        @functools.wraps(f)
        def curry(*args, **kwargs):
            if datetime.datetime.now() > deadline:
                _reset()
            elif next(count) >= treshold:
                hottest_args = sorted(
                    [item for item in calls_counters.items()],
                    key=lambda item: item[1],
                )[0]
                log.warning(
                    "Invocation surge detected. func=%s, hottest_args=%s",
                    f"{f.__module__}.{f.__qualname__}",
                    hottest_args,
                )
                _reset()
            key = f"{args}{kwargs}"
            calls_counters[key] = calls_counters.get(key, 0) + 1
        return curry
    return wrapped
