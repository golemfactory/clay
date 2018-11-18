import unittest
import uuid
from datetime import timedelta

from freezegun import freeze_time

from golem.task.timer import ActionTimer, ActionTimers, ThirstTimer


class TestActionTimer(unittest.TestCase):

    # pylint: disable=no-member,no-self-argument

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_started(frozen_time, _):
        timer = ActionTimer()
        assert not timer._started
        assert timer._finished

        timer.start()
        assert timer._started
        assert not timer._finished

        frozen_time.tick(timedelta(seconds=5))
        timer.start()
        assert timer._started
        assert not timer._finished

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_finished(frozen_time, _):
        timer = ActionTimer()
        finished = timer._finished

        timer.finish()

        assert timer._finished == finished

        timer.start()
        frozen_time.tick(timedelta(seconds=5))
        timer.finish()

        assert timer._finished == finished + 5.


class TestThirstTimer(unittest.TestCase):

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_thirst_decrease(frozen_time, _):
        timer = ThirstTimer()
        thirst = timer.thirst
        frozen_time.tick(timedelta(seconds=5))
        assert thirst > timer.thirst

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_thirst_increase(frozen_time, _):
        timer = ThirstTimer()
        thirst = timer.thirst
        timer.start()
        frozen_time.tick(timedelta(seconds=5))
        timer.finish()
        assert thirst < timer.thirst


class TestActionTimers(unittest.TestCase):

    # pylint: disable=no-member,no-self-argument

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_started(frozen_time, _):
        timers = ActionTimers()
        identifier = str(uuid.uuid4())

        frozen_time.tick(timedelta(seconds=5))
        timers.start(identifier)

        timer = timers._history[identifier]
        assert isinstance(timer, ActionTimer)
        assert timer._started
        assert not timer.finished

        started = timer._started

        frozen_time.tick(timedelta(seconds=5))
        timers.start(identifier)

        timer = timers._history[identifier]
        assert isinstance(timer, ActionTimer)
        assert not timer.finished
        assert timer._started == started + 5

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_finished(frozen_time, self):
        timer = ActionTimers()
        identifier = str(uuid.uuid4())

        with self.assertRaises(KeyError):
            assert timer.time(identifier) is None

        timer.start(identifier)
        frozen_time.tick(timedelta(seconds=5))
        timer.finish(identifier)
        assert timer.time(identifier) == 5

        # second call should return the same value
        timer.finish(identifier)
        assert timer.time(identifier) == 5

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_remove(frozen_time, self):
        timer = ActionTimers()
        identifier = str(uuid.uuid4())

        with self.assertRaises(KeyError):
            timer.remove(identifier)

        timer.start(identifier)
        frozen_time.tick(timedelta(seconds=5))
        assert timer.remove(identifier) is None

        with self.assertRaises(KeyError):
            timer.remove(identifier)

        timer.start(identifier)
        frozen_time.tick(timedelta(seconds=5))
        timer.finish(identifier)

        assert timer.remove(identifier) == 5
