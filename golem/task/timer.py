import logging
import time
from typing import Optional


logger = logging.getLogger(__name__)


class ComputeTimer:
    """ Keeps track of computation / idle time per Golem session """

    def __init__(self):
        self._time_comp: float = 0.
        self._time_idle: float = 0.

        self._time_started: Optional[float] = None
        self._time_finished: Optional[float] = time.time()

    def time_computing(self) -> float:
        """ Returns the total computation time. If computing, returns the
            accumulated value enlarged by the time since computation started.
        """
        if self._time_started is None:
            return self._time_comp
        return self._time_comp + time.time() - self._time_started

    def time_idle(self) -> float:
        """ Returns the total idle time. If not computing, returns the
            accumulated value enlarged by the time since last computation.
        """
        if self._time_finished is None:
            return self._time_idle
        return self._time_idle + time.time() - self._time_finished

    def start(self) -> None:
        """ Updates the state to keep track of computation time and increases
            the accumulated idle time.

            This method forces the correct class state.
        """

        now = time.time()

        if self._time_finished is None:
            logger.error("Computation was not finished")
        else:
            self._time_idle += now - self._time_finished

        self._time_started = now
        self._time_finished = None

    def stop(self) -> None:
        """ Updates the state to keep track of idle time and increases
            the accumulated computation time.
        """

        if self._time_started is None:
            logger.debug("Computation is not running")
            return

        now = time.time()

        self._time_comp += now - self._time_started
        self._time_started = None
        self._time_finished = now


ProviderComputeTimer = ComputeTimer()  # noqa
