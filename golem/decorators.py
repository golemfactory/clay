import functools
import logging

from golem import model

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


def run_with_db():
    """Run only when DB is active"""
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
