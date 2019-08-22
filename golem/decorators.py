import functools
import logging

from golem import model

log = logging.getLogger('golem.decorators')


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
