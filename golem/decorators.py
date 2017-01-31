import functools
import logging

log = logging.getLogger('golem.decorators')


def log_error(reraise=False):
    def _curry(f):
        @functools.wraps(f)
        def _wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except:
                log.exception('Error in %r', f)
                if reraise:
                    raise
        return _wrapper
    return _curry
