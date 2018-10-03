import logging
import time
from typing import Optional


logger = logging.getLogger(__name__)


class IdleTimer:
    """ Keeps track of idle time per Golem session """

    def __init__(self):
        self._time_idle: float = 0.
        self._last_comp_finished: Optional[float] = time.time()

    def time_idle(self) -> float:
        """ Returns the total idle time. If not computing, returns the
            accumulated value enlarged by the time since last computation.
        """
        if self._last_comp_finished is None:
            return self._time_idle
        return self._time_idle + time.time() - self._last_comp_finished

    def comp_started(self) -> None:
        """ Updates the state to keep track of computation time and increases
            the accumulated idle time.

            This method forces the correct object state.
        """

        if self._last_comp_finished is None:
            logger.error("Computation was not finished")
        else:
            self._time_idle += time.time() - self._last_comp_finished

        self._last_comp_finished = None

    def comp_finished(self) -> None:
        """ Updates the state to keep track of idle time and increases
            the accumulated computation time.
        """

        if self._last_comp_finished is None:
            self._last_comp_finished = time.time()
        else:
            logger.debug("Computation is not running")


ProviderIdleTimer = IdleTimer()  # noqa
