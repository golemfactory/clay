import asyncio
import functools
import logging
import queue
import threading
from typing import Callable, Optional

from pydispatch import dispatcher
from twisted.internet import defer
from twisted.internet import task as twisted_task
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
# DISPATCHING
##


_TO_ASYNCIO: queue.Queue = queue.Queue()
_TO_TWISTED: queue.Queue = queue.Queue()


def dispatch_from(queue_: queue.Queue):
    try:
        kwargs = queue_.get_nowait()
    except queue.Empty:
        pass
    else:
        dispatcher.send(**kwargs)


def asyncio_dispatch(**kwargs):
    global _TO_ASYNCIO
    _TO_ASYNCIO.put_nowait(kwargs)


def twisted_dispatch(**kwargs):
    global _TO_TWISTED
    _TO_TWISTED.put_nowait(kwargs)


def asyncio_listen():
    def wrapper(f):
        @functools.wraps(f)
        def curry(**kwargs):
            if threading.current_thread().name != _ASYNCIO_ID:
                asyncio_dispatch(**kwargs)
                return
            f(**kwargs)
        return curry
    return wrapper


##
# ASYNCIO
##

_ASYNCIO_ID = 'Thread-aio'
_RUN = threading.Event()


@defer.inlineCallbacks
def start_asyncio_thread():
    asyncio_thread = threading.Thread(
        target=asyncio_start,
        name=_ASYNCIO_ID,
    )
    counter = 0
    def listener(**kwargs):
        nonlocal counter
        print('IN TWISTED', threading.current_thread().name, kwargs)
        counter += 1
        dispatcher.send(signal='asyncio', nonce=counter)
    dispatcher.connect(listener, signal='twisted', weak=False)
    asyncio_thread.start()
    loop = twisted_task.LoopingCall(
        functools.partial(dispatch_from, _TO_TWISTED),
    )
    yield loop.start(1.0)


def asyncio_start():
    @asyncio_listen()
    def listener(**kwargs):
        print('IN ASYNCIO', threading.current_thread().name, kwargs)
    dispatcher.connect(listener, signal='asyncio')
    _RUN.set()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(asyncio_main())


def asyncio_stop():
    global _RUN
    print('Stopping ASYNCIO')
    _RUN.clear()


async def asyncio_main():
    counter = 0
    global _RUN
    print('ASYNCIO started', threading.current_thread().name)
    while _RUN.is_set():
        print(str(counter)+'*'*80, threading.current_thread().name)
        twisted_dispatch(signal="twisted", nonce=counter)
        counter += 1
        dispatch_from(_TO_ASYNCIO)
        await asyncio.sleep(1)
    print("ASYNCIO finished")
