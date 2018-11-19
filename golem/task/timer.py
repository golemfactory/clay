import logging
import math
import time
from typing import ClassVar, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class ActionTimer:
    """ Keeps track of computation timestamps per Golem session """

    def __init__(self) -> None:
        self._started: Optional[float] = None
        self._finished: Optional[float] = time.time()

    @property
    def finished(self) -> bool:
        return self._finished is not None

    @property
    def time(self) -> Optional[float]:
        """ Returns the time spent on an action or None
        """
        if None in (self._started, self._finished):
            return None
        return self._finished - self._started  # type: ignore

    def start(self) -> None:
        """ Updates the started and finished (= None) timestamps.
        """
        logger.debug("ActionTimer.comp_started() at %r", time.time())

        if self._finished is None:
            logger.error("action was not finished")

        self._started = time.time()
        self._finished = None

    def finish(self) -> None:
        """ Updates the finished timestamp.
        """
        logger.debug("ActionTimer.comp_finished() at %r", time.time())

        if self._finished is None and self._started:
            self._finish()
        else:
            logger.warning("action is not running")

    def _finish(self) -> None:
        self._finished = time.time()


class ThirstTimer(ActionTimer):

    _ALPHA: ClassVar[float] = 0.00001
    _BETA: ClassVar[float] = 4 * _ALPHA

    def __init__(self) -> None:
        super().__init__()
        self._thirst = 0.2

    @property
    def thirst(self):
        return self._thirst *\
            math.exp(-self._ALPHA * (time.time() - self._finished))

    def _finish(self) -> None:
        super()._finish()

        comp_length = self._finished - self._started  # type: ignore
        self._thirst = math.exp(self._BETA * comp_length) * self._thirst


class ActionTimers:
    """ Keeps track of started / finished timestamps of multiple actions """

    def __init__(self):
        self._history: Dict[str, ActionTimer] = dict()

    def time(self, identifier: str) -> Optional[float]:
        """ Returns time spent on an action; None if action hasn't
            been finished yet. Throws a KeyError if identifier is not known.
        """
        return self._history[identifier].time

    def start(self, identifier: str) -> None:
        """ Initializes the start and finished (= None) timestamps.
        """
        logger.debug("ActionTimers.start(%s) at %r",
                     identifier, time.time())

        timer = ActionTimer()
        timer.start()
        self._history[identifier] = timer

    def finish(self, identifier: str) -> None:
        """ Updates the finished timestamp.
        """
        timer = self._history.get(identifier)
        if timer and not timer.finished:
            logger.debug("ActionTimers.finish(%s) at %r",
                         identifier, time.time())
            timer.finish()

    def remove(self, identifier: str) -> Optional[float]:
        """ Removes the identifier from history. Throws a KeyError if identifier
            is not known.
        """
        return self._history.pop(identifier).time


ProviderTimer = ThirstTimer()  # noqa
ProviderComputeTimers = ActionTimers()  # noqa
