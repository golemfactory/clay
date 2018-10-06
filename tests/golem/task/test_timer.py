import unittest
from datetime import timedelta

from freezegun import freeze_time

from golem.task.timer import IdleTimer


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
