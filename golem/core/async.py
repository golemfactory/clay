import logging

from twisted.internet import threads
from twisted.internet.defer import succeed
from twisted.web.client import Agent
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

log = logging.getLogger(__name__)


class AsyncHTTPRequest:

    agent = None
    timeout = 5

    @implementer(IBodyProducer)
    class BytesBodyProducer:

        def __init__(self, body):
            self.body = body
            self.length = len(body)

        def startProducing(self, consumer):
            consumer.write(self.body)
            return succeed(None)

        def pauseProducing(self):
            pass

        def resumeProducing(self):
            pass

        def stopProducing(self):
            pass

    @classmethod
    def run(cls, method, uri, headers, body):
        if not cls.agent:
            from twisted.internet import reactor
            cls.agent = Agent(reactor, connectTimeout=cls.timeout)

        return cls.agent.request(method, uri, headers,
                                 cls.BytesBodyProducer(body))


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
        deferred.addCallback(success)
    deferred.addErrback(error)
    return deferred

  
def async_callback(func):
    def callback(result):
        return async_run(AsyncRequest(func, result))
    return callback


def default_errback(failure):
    log.error('Caught async exception:\n%s', failure.getTraceback())
