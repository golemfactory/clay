import logging
import time
from typing import Optional, Dict, Tuple

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
        logger.debug("IdleTimer.comp_started() at %r", time.time())

        if self._last_comp_finished is None:
            logger.error("Computation was not finished")
        else:
            self._time_idle += time.time() - self._last_comp_finished

        self._last_comp_finished = None

    def comp_finished(self) -> None:
        """ Updates the state to keep track of idle time and increases
            the accumulated computation time.
        """
        logger.debug("IdleTimer.comp_finished() at %r", time.time())

        if self._last_comp_finished is None:
            self._last_comp_finished = time.time()
        else:
            logger.warning("Computation is not running")


ComputeTimeTuple = Tuple[float, Optional[float]]


class ComputeTimers:
    """ Keeps track of subtask computation time per Golem session """

    def __init__(self):
        self._comp_history: Dict[str, ComputeTimeTuple] = dict()

    def time_computing(self, identifier: str) -> Optional[float]:
        """ Returns computation time per subtask. Returns None if computation
            hasn't finished yet. Throws a KeyError if identifier is not known.
        """

        return self._comp_time(self._comp_history[identifier])

    def comp_started(self, identifier: str) -> None:
        """ Initializes the start and finished (= None) computation points in
            time.
        """
        logger.debug("ComputeTimers: started computation of %s at %r",
                     identifier, time.time())

        self._comp_history[identifier] = (time.time(), None)

    def comp_finished(self, identifier: str) -> None:
        """ Updates the finished (= None) computation point in time
            for an identifier and returns the computation time.
        """

        if identifier not in self._comp_history:
            return

        logger.debug("ComputeTimers: finished computation of %s at %r",
                     identifier, time.time())

        entry = self._comp_history[identifier]
        if entry[1] is not None:
            return

        self._comp_history[identifier] = (entry[0], time.time())

    def remove(self, identifier: str) -> Optional[float]:
        """ Removes the identifier from history. Throws a KeyError if identifier
            is not known.
        """

        entry = self._comp_history.pop(identifier)
        return self._comp_time(entry)

    @staticmethod
    def _comp_time(entry: ComputeTimeTuple) -> Optional[float]:
        if entry[1] is None:
            return None
        return entry[1] - entry[0]


ProviderIdleTimer = IdleTimer()  # noqa
ProviderComputeTimers = ComputeTimers()  # noqa
