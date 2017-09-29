import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=10)


class LoopingCall:

    def __init__(self, f, *args, **kwargs):
        self.f = f
        self.args = args
        self.kwargs = kwargs
        self._running = False
        self._now = True
        self._interval = 1

    def start(self, interval, now=True):
        self._running = True
        self._now = now
        self._interval = interval

        return asyncio.ensure_future(self._run())

    def stop(self):
        self._running = False

    @property
    def running(self):
        return self._running

    async def _run(self):
        if not self._now:
            await asyncio.sleep(self._interval)
        while self._running:
            self.f(*self.args, **self.kwargs)
            await asyncio.sleep(self._interval)


def handle_future(future, success=None, error=None):
    assert isinstance(future, asyncio.Future)

    def handler(f):
        try:
            result = f.result()
        except Exception as exc:
            error and error(exc)
        else:
            success and success(result)

    future.add_done_callback(handler)


def run_threaded(method, *args, success=None, error=None):
    """Execute a deferred job in a separate thread"""
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(executor, method, *args)
    handle_future(future, success, error or default_errback)
    return future


def async_queue(method, *args):
    return asyncio.get_event_loop().call_soon(method, *args)


def async_queue_threadsafe(method, *args):
    return asyncio.get_event_loop().call_soon_threadsafe(method, *args)


def default_errback(failure, *args):
    log.error('Caught async exception:\n%s (%r)', failure, args or 'None')
