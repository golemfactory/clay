import logging

from gevent.threadpool import ThreadPool
from twisted.internet.defer import Deferred

log = logging.getLogger(__name__)


_thread_pool = ThreadPool(30)


class AsyncRequest(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args or []
        self.kwargs = kwargs or {}


def async_run(async_request, success=None, error=None):
    deferred = Deferred()

    if success:
        deferred.addCallback(success)
    if error:
        deferred.addErrback(error)
    else:
        deferred.addErrback(default_errback)

    def wrapper():
        try:
            result = async_request.method(*async_request.args,
                                          **async_request.kwargs)
        except Exception as exc:
            deferred.errback(exc)
        else:
            deferred.callback(result)

    _thread_pool.spawn(wrapper)
    return deferred


def default_errback(failure):
    log.error('Caught async exception:\n%s', failure.getTraceback())
