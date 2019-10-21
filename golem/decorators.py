import functools
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
