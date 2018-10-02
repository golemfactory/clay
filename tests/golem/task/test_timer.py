import unittest
from datetime import timedelta

from freezegun import freeze_time

from golem.task.timer import ComputeTimer


class TestComputeTimer(unittest.TestCase):

    # pylint: disable=no-member,no-self-argument

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_start(frozen_time, _):
        timer = ComputeTimer()

        assert not timer._time_started
        assert timer._time_finished

        timer.start()

        assert timer._time_started
        assert not timer._time_finished

        started = timer._time_started
        frozen_time.tick(timedelta(seconds=5))
        timer.start()

        assert timer._time_started > started
        assert not timer._time_finished

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_stop(frozen_time, _):
        timer = ComputeTimer()
        finished = timer._time_finished

        timer.stop()

        assert not timer._time_started
        assert timer._time_finished == finished

        timer.start()
        frozen_time.tick(timedelta(seconds=5))
        timer.stop()

        assert not timer._time_started
        assert timer._time_finished

        finished = timer._time_finished
        frozen_time.tick(timedelta(seconds=5))
        timer.stop()

        assert not timer._time_started
        assert timer._time_finished == finished

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_computing_time(frozen_time, _):
        timer = ComputeTimer()

        timer.start()
        frozen_time.tick(timedelta(seconds=5))
        timer.stop()

        assert timer.time_computing() == 5.

        timer.start()
        frozen_time.tick(timedelta(seconds=5))
        timer.stop()

        assert timer.time_computing() == 10.

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_idle_time(frozen_time, _):
        timer = ComputeTimer()
        frozen_time.tick(timedelta(seconds=5))

        timer.start()
        assert timer.time_idle() == 5.

        frozen_time.tick(timedelta(seconds=5))
        timer.stop()

        assert timer.time_idle() == 5.

        frozen_time.tick(timedelta(seconds=5))
        timer.start()
        assert timer.time_idle() == 10.
