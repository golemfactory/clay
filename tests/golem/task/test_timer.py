import time
import unittest
import uuid
from datetime import timedelta

from freezegun import freeze_time

from golem.task.timer import IdleTimer, ComputeTimers


class TestIdleTimer(unittest.TestCase):

    # pylint: disable=no-member,no-self-argument

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_comp_started(frozen_time, _):
        timer = IdleTimer()
        assert not timer.last_comp_started
        assert timer.last_comp_finished

        timer.comp_started()
        assert timer.last_comp_started
        assert not timer.last_comp_finished

        frozen_time.tick(timedelta(seconds=5))
        timer.comp_started()
        assert timer.last_comp_started
        assert not timer.last_comp_finished

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_comp_finished(frozen_time, _):
        timer = IdleTimer()
        finished = timer.last_comp_finished

        timer.comp_finished()

        assert timer.last_comp_finished == finished

        timer.comp_started()
        frozen_time.tick(timedelta(seconds=5))
        timer.comp_finished()

        assert timer.last_comp_finished == finished + 5.

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_thirst_decrease(frozen_time, _):
        timer = IdleTimer()
        thirst = timer.thirst
        frozen_time.tick(timedelta(seconds=5))
        assert thirst > timer.thirst

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_thirst_increase(frozen_time, _):
        timer = IdleTimer()
        thirst = timer.thirst
        timer.comp_started()
        frozen_time.tick(timedelta(seconds=5))
        timer.comp_finished()
        assert thirst < timer.thirst


class TestComputeTimers(unittest.TestCase):

    # pylint: disable=no-member,no-self-argument

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_comp_started(frozen_time, _):
        timer = ComputeTimers()
        identifier = str(uuid.uuid4())

        frozen_time.tick(timedelta(seconds=5))
        timer.comp_started(identifier)

        entry = timer._comp_history[identifier]
        assert entry == (time.time(), None)

        frozen_time.tick(timedelta(seconds=5))
        timer.comp_started(identifier)

        entry = timer._comp_history[identifier]
        assert entry == (time.time(), None)

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_comp_finished(frozen_time, self):
        timer = ComputeTimers()
        identifier = str(uuid.uuid4())

        with self.assertRaises(KeyError):
            assert timer.time_computing(identifier) is None

        timer.comp_started(identifier)
        frozen_time.tick(timedelta(seconds=5))
        timer.comp_finished(identifier)
        assert timer.time_computing(identifier) == 5

        # second call should return the same value
        timer.comp_finished(identifier)
        assert timer.time_computing(identifier) == 5

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_remove(frozen_time, self):
        timer = ComputeTimers()
        identifier = str(uuid.uuid4())

        with self.assertRaises(KeyError):
            timer.remove(identifier)

        timer.comp_started(identifier)
        frozen_time.tick(timedelta(seconds=5))
        assert timer.remove(identifier) is None

        with self.assertRaises(KeyError):
            timer.remove(identifier)

        timer.comp_started(identifier)
        frozen_time.tick(timedelta(seconds=5))
        timer.comp_finished(identifier)

        assert timer.remove(identifier) == 5
