import datetime
import functools
import logging

log = logging.getLogger('golem.decorators')


def log_error(reraise=False):
    def _curry(f):
        @functools.wraps(f)
        def _wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception:  # pylint: disable=broad-except
                log.exception('Error in %r', f)
                if reraise:
                    raise
        return _wrapper
    return _curry


def run_at_most_every(delta: datetime.timedelta):
    # SEE golem.core.golem_async.run_at_most_every
    # for asyncio implementation
    last_run = datetime.datetime.min

    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            nonlocal last_run
            if datetime.datetime.now() - last_run < delta:
                return None
            last_run = datetime.datetime.now()
            return f(*args, **kwargs)
        return curry
    return wrapped

daily = functools.partial(run_at_most_every, delta=datetime.timedelta(days=1))
