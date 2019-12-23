import asyncio
import concurrent.futures
import datetime
import functools
import logging
from typing import Any, Callable, Dict, Optional

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


##
# ASYNCIO
##

_ASYNCIO_THREAD_POOL = concurrent.futures.ThreadPoolExecutor()


def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:  # no event loop in current thread
        from twisted.internet import reactor
        return reactor._asyncioEventloop


def soon():
    "Run non-async function in next iteration of event loop"
    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            loop = get_event_loop()
            loop.call_soon_threadsafe(
                functools.partial(
                    f,
                    *args,
                    **kwargs,
                ),
            )
            return None
        return curry
    return wrapped


def taskify():
    "Run async function as a Task in current loop"
    def wrapped(f):
        assert asyncio.iscoroutinefunction(f)

        @functools.wraps(f)
        def curry(*args, **kwargs):
            task = asyncio.ensure_future(
                f(*args, **kwargs),
                loop=get_event_loop()
            )
            return task
        return curry
    return wrapped


def throttle(delta: datetime.timedelta):
    """Invoke the decorated function only once per `delta`

    All subsequent call will be dropped until delta passes.
    """
    last_run = datetime.datetime.min

    def wrapped(f):
        @functools.wraps(f)
        async def curry(*args, **kwargs):
            nonlocal last_run
            current_delta = datetime.datetime.now() - last_run
            if current_delta < delta:
                return
            last_run = datetime.datetime.now()
            result = f(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        return curry
    return wrapped


def run_in_thread():
    # Use for IO bound operations
    # noqa SEE: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor  pylint: disable=line-too-long
    def wrapped(f):
        # No coroutines in a pool
        assert not asyncio.iscoroutinefunction(f)

        @functools.wraps(f)
        async def curry(*args, **kwargs):
            loop = get_event_loop()
            return await loop.run_in_executor(
                executor=_ASYNCIO_THREAD_POOL,
                func=functools.partial(
                    f,
                    *args,
                    **kwargs,
                    loop=loop,
                ),
            )
        return curry
    return wrapped


class CallScheduler:
    def __init__(self):
        self._timers: Dict[str, asyncio.TimerHandle] = dict()

    def schedule(
            self,
            key: str,
            timeout: float,
            call: Callable[..., Any],
    ) -> None:
        def on_timeout():
            self._timers.pop(key, None)
            call()

        loop = asyncio.get_event_loop()

        self.cancel(key)
        self._timers[key] = loop.call_at(
            loop.time() + timeout,
            on_timeout)

    def cancel(self, key):
        timer = self._timers.pop(key, None)
        if timer:
            timer.cancel()
