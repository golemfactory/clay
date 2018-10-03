import unittest
from datetime import timedelta

from freezegun import freeze_time

from golem.task.timer import IdleTimer


class TestIdleTimer(unittest.TestCase):

    # pylint: disable=no-member,no-self-argument

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_comp_started(frozen_time, _):
        timer = IdleTimer()
        assert timer._last_comp_finished

        timer.comp_started()
        assert not timer._last_comp_finished

        frozen_time.tick(timedelta(seconds=5))
        timer.comp_started()
        assert not timer._last_comp_finished

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_comp_finished(frozen_time, _):
        timer = IdleTimer()
        finished = timer._last_comp_finished

        timer.comp_finished()

        assert timer._last_comp_finished == finished

        timer.comp_started()
        frozen_time.tick(timedelta(seconds=5))
        timer.comp_finished()

        assert timer._last_comp_finished == finished + 5.

    @freeze_time("2018-01-01 00:00:00", as_arg=True)
    def test_idle_time(frozen_time, _):
        timer = IdleTimer()
        frozen_time.tick(timedelta(seconds=5))

        timer.comp_started()
        assert timer.time_idle() == 5.

        frozen_time.tick(timedelta(seconds=5))
        timer.comp_finished()

        assert timer.time_idle() == 5.

        frozen_time.tick(timedelta(seconds=5))
        timer.comp_started()
        assert timer.time_idle() == 10.
