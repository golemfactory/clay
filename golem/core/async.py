import functools
import logging
from typing import Callable, Optional

from twisted.internet import defer
from twisted.internet import threads
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

logger = logging.getLogger(__name__)


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
            return defer.succeed(None)

        def pauseProducing(self):
            pass

        def resumeProducing(self):
            pass

        def stopProducing(self):
            pass

    @classmethod
    def run(cls, method, uri, headers, body):
        if not cls.agent:
            cls.agent = cls.create_agent()
        return cls.agent.request(method, uri, headers,
                                 cls.BytesBodyProducer(body))

    @classmethod
    def create_agent(cls):
        from twisted.internet import reactor
        from twisted.web.client import Agent  # imports reactor
        return Agent(reactor, connectTimeout=cls.timeout)


class AsyncRequest(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args or []
        self.kwargs = kwargs or {}


def async_run(deferred_call: AsyncRequest, success: Optional[Callable] = None,
              error: Optional[Callable] = None):
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


def default_errback(failure):
    logger.error('Caught async exception:\n%s', failure.getTraceback())
    return failure  # return the failure to continue with the errback chain


def deferred_run():
    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            # Import reactor only when it is necessary;
            # otherwise process-wide signal handlers may be installed
            from twisted.internet import reactor
            if reactor.running:
                execute = threads.deferToThread
            else:
                logger.debug(
                    'Reactor not running.'
                    ' Switching to blocking call for %r',
                    f,
                )
                execute = defer.execute
            return execute(f, *args, **kwargs)
        return curry
    return wrapped
