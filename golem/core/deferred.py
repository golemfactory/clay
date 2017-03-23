
from twisted.internet.defer import DebugInfo


def install_event_logger():
    import logging
    logger = logging.getLogger('golem')

    def delete(self):
        if self.failResult is not None:
            logger.error("Unhandled error in Deferred:\n{}"
                         .format(self.failResult))

    setattr(DebugInfo, '__del__', delete)
