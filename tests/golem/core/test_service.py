import logging
from io import StringIO
from unittest import TestCase

import pytest
from golem.core.service import LoopingCallService, log
from golem.tools.testwithreactor import TestWithReactor
from twisted.internet.task import Clock


def test_service_start_stop():
    service = LoopingCallService()
    assert not service.running
    service.start()
    assert service.running
    service.stop()
    assert not service.running


def test_service_invalid_start():
    service = LoopingCallService()
    service.start()
    with pytest.raises(RuntimeError):
        service.start()
    with pytest.raises(RuntimeError):
        service.start()


def test_service_invalid_stop():
    service = LoopingCallService()
    with pytest.raises(RuntimeError):
        service.stop()
    with pytest.raises(RuntimeError):
        service.stop()
    service.start()
    service.stop()
    with pytest.raises(RuntimeError):
        service.stop()
    with pytest.raises(RuntimeError):
        service.stop()


class CountingService(LoopingCallService):
    def __init__(self):
        super().__init__(run_in_thread=True)
        self.clock = Clock()
        self.count = 0
        # Mock the real clock.
        self._loopingCall.clock = self.clock

    def _run_async(self):
        self.count += 1


class AsyncCountingService(LoopingCallService):
    def __init__(self):
        super().__init__(run_in_thread=True)
        self.count = 0

    def _run(self):
        self.count += 1


class ExceptionalService(LoopingCallService):
    def __init__(self, delay):
        super().__init__(run_in_thread=True)
        self.initial_delay = delay
        self.delay = 0
        self.clock = Clock()
        # Mock the real clock.
        self._loopingCall.clock = self.clock

    def start(self):
        self.delay = self.initial_delay
        super(ExceptionalService, self).start()

    def _run_async(self):
        if self.delay == 0:
            raise RuntimeError("service error")
        self.delay -= 1


class TestService(TestWithReactor):

    def test_run_async(self):
        import time

        asys = AsyncCountingService()
        asys.start()
        time.sleep(0.5)
        assert asys.count > 0


class TestCountingService(TestCase):

    def test_service_run_once(self):
        cs = CountingService()
        assert not cs.running
        cs.start()
        cs.stop()
        # Service should run once on start().
        assert cs.count == 1

    def test_service_run(self):
        cs = CountingService()
        assert not cs.running
        cs.start()
        assert cs.count == 1
        # Advance the clock not to reach the next call.
        cs.clock.advance(0.9)
        assert cs.count == 1
        ticks = (1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7)
        # Advance clock multiple times. For each advance over 1 second we get only
        # one call, no matter the value.
        cs.clock.pump(ticks)
        assert cs.count == 1 + len(ticks)
        cs.stop()
        # When service is stopped _run should not be called any more.
        cs.clock.advance(2)
        assert cs.count == 1 + len(ticks)


class TestExceptionalService(TestCase):

    def test_service_exception_on_start(self):
        err = StringIO()
        hdlr = logging.StreamHandler(err)
        log.addHandler(hdlr)
        service = ExceptionalService(0)
        service.start()
        assert "Service Error:" in err.getvalue()
        assert not service.running  # After service error it should be stopped.
        log.removeHandler(hdlr)

    def test_service_exception_delayed(self):
        err = StringIO()
        hdlr = logging.StreamHandler(err)
        log.addHandler(hdlr)
        service = ExceptionalService(1)
        service.start()
        assert err.getvalue() is ""
        assert service.running

        service.clock.advance(99)
        errmsg = err.getvalue()
        assert "Service Error:" in errmsg
        assert not service.running

        service.clock.advance(44)
        assert err.getvalue() == errmsg  # No new errors expected.
        assert not service.running       # The service still stopped.

        service.start()
        assert service.running           # But can be started again.

        log.removeHandler(hdlr)
