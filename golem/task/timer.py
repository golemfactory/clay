import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class IdleTimer:
    """ Keeps track of computation timestamps per Golem session """

    def __init__(self):
        self._last_comp_started: Optional[float] = None
        self._last_comp_finished: Optional[float] = time.time()

    @property
    def last_comp_started(self) -> Optional[float]:
        return self._last_comp_started

    @property
    def last_comp_finished(self) -> Optional[float]:
        return self._last_comp_finished

    def comp_started(self) -> None:
        """ Updates the computation started and finished timestamps. """

        logger.debug("IdleTimer.comp_started() at %r", time.time())

        if self._last_comp_finished is None:
            logger.error("Computation was not finished")

        self._last_comp_started = time.time()
        self._last_comp_finished = None

    def comp_finished(self) -> None:
        """ Updates the computation finished timestamp. """

        logger.debug("IdleTimer.comp_finished() at %r", time.time())

        if self._last_comp_finished is None:
            self._last_comp_finished = time.time()
        else:
            logger.warning("Computation is not running")


ProviderIdleTimer = IdleTimer()  # noqa
