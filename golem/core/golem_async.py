import asyncio
import concurrent.futures
import datetime
import functools
import logging
import threading
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


##
# ASYNCIO
##

_ASYNCIO_THREAD_POOL = concurrent.futures.ThreadPoolExecutor()


def soon():
    "Run non-async function in next iteration of event loop"
    def wrapped(f):
        @functools.wraps(f)
        def curry(*args, **kwargs):
            loop = asyncio.get_event_loop()
            loop.call_soon(
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
        @functools.wraps(f)
        def curry(*args, **kwargs):
            task = asyncio.ensure_future(
                functools.partial(
                    f,
                    *args,
                    **kwargs,
                ),
            )
            return task
        return curry
    return wrapped


def run_at_most_every(delta: datetime.timedelta):
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
            return await asyncio.get_event_loop().run_in_executor(
                executor=_ASYNCIO_THREAD_POOL,
                func=functools.partial(
                    f,
                    *args,
                    **kwargs,
                    loop=asyncio.get_event_loop(),
                ),
            )
        return curry
    return wrapped


def locked():
    lock = asyncio.Lock()

    def wrapped(f):
        @functools.wraps(f)
        async def curry(*args, **kwargs):
            nonlocal lock
            async with lock:
                result = f(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
        return curry
    return wrapped


def asyncio_run(coro):
    """Simulate asyncio.run() from python3.7"""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def asyncio_start():
    global _ASYNCIO_TASKS  # pylint: disable=global-statement
    _ASYNCIO_RUN.set()
    logger.info(
        'ASYNCIO thread started. name=%r',
        threading.current_thread().name,
    )
    loop = asyncio.new_event_loop()
    _ASYNCIO_TASKS = asyncio.Queue(loop=loop)
    loop.set_debug(True)
    asyncio.set_event_loop(loop)
    asyncio_run(asyncio_main())
    logger.info("ASYNCIO thread finished")


async def asyncio_main():
    wait_task = asyncio.ensure_future(_asyncio_wait_for_tasks())
    while _ASYNCIO_RUN.is_set():
        try:
            await _asyncio_process_thread_queue()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error in asyncio main loop")
        await asyncio.sleep(0.1)
    logger.info('Cleaning up ASYNCIO queue. size=%r', _ASYNCIO_TASKS.qsize())
    await _ASYNCIO_TASKS.join()
    wait_task.cancel()
