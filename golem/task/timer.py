import logging
import time
from typing import ClassVar, Optional


logger = logging.getLogger(__name__)


class ProviderComputeTimer:
    """ Keeps track of provider's computation / idle time per Golem session """

    _time_comp: ClassVar[float] = 0
    _time_idle: ClassVar[float] = 0

    _time_started: ClassVar[Optional[float]] = None
    _time_finished: ClassVar[Optional[float]] = time.time()

    @classmethod
    def time_computing(cls) -> float:
        """ Returns the total computation time. If computing, returns the
            accumulated value enlarged by the time since computation started.
        """
        if cls._time_started is None:
            return cls._time_comp
        return cls._time_comp + time.time() - cls._time_started

    @classmethod
    def time_idle(cls) -> float:
        """ Returns the total idle time. If not computing, returns the
            accumulated value enlarged by the time since last computation.
        """
        if cls._time_finished is None:
            return cls._time_idle
        return cls._time_idle + time.time() - cls._time_finished

    @classmethod
    def start(cls) -> None:
        """ Updates the state to keep track of computation time and increases
            the accumulated idle time.

            This method forces the correct class state.
        """

        now = time.time()

        if cls._time_finished is None:
            logger.error("Computation was not finished")
        else:
            cls._time_idle += now - cls._time_finished

        cls._time_started = now
        cls._time_finished = None

    @classmethod
    def stop(cls) -> None:
        """ Updates the state to keep track of idle time and increases
            the accumulated computation time.
        """

        if cls._time_started is None:
            logger.debug("Computation is not running")
            return

        now = time.time()

        cls._time_comp += now - cls._time_started
        cls._time_started = None
        cls._time_finished = now
