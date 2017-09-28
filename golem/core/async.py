import asyncio
import logging

log = logging.getLogger(__name__)


class AsyncRequest:

    """ Deferred job descriptor """

    def __init__(self, method, *args):
        self.method = method
        self.args = args or []


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


def async_run(call, success=None, error=None):
    """Execute a deferred job in a separate thread"""
    error = error or default_errback

    def done(f):
        try:
            result = f.result()
            if success:
                success(result)
        except Exception as exc:
            if error:
                error(exc)

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, call.method, *call.args)
    future.add_done_callback(done)
    return future


# FIXME: unify / introduce pooling
def run_in_executor(method, *args, success=None, error=None):
    error = error or default_errback

    import traceback
    tb = traceback.format_stack()

    def done(f):
        try:
            result = f.result()
            if success:
                success(result)
        except Exception as exc:
            if error:
                error(exc, tb)

    future = asyncio.get_event_loop().run_in_executor(None, method, *args)
    future.add_done_callback(done)
    return future


def async_callback(func):
    def callback(result):
        return async_run(AsyncRequest(func, result))
    return callback


def default_errback(failure, *args):
    log.error('Caught async exception:\n%s (%r)', failure, args or 'None')
