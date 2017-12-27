import logging
from twisted.internet import threads

log = logging.getLogger(__name__)


class AsyncRequest(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args or []
        self.kwargs = kwargs or {}


def async_run(deferred_call, success=None, error=None):
    """Execute a deferred job in a separate thread (Twisted)"""
    deferred = threads.deferToThread(deferred_call.method,
                                     *deferred_call.args,
                                     **deferred_call.kwargs)
    if error is None:
        error = default_errback
    if success:
        deferred.addCallback(wrap_callback(success))
    deferred.addErrback(wrap_callback(error))
    return deferred


def wrap_callback(func):
    from twisted.internet import reactor

    def wrapped(*args, **kwargs):
        return reactor.callFromThread(func, *args, **kwargs)
    return wrapped

  
def async_callback(func):
    def callback(result):
        return async_run(AsyncRequest(func, result))
    return callback


def default_errback(failure):
    log.error('Caught async exception:\n%s', failure.getTraceback())
