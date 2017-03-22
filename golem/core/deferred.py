from twisted.logger import LogLevel
from twisted.logger import globalLogPublisher


def install_event_logger():
    import logging
    logger = logging.getLogger('golem')
    event_logger = _create_event_logger(logger)
    globalLogPublisher.addObserver(event_logger)


def _create_event_logger(logger):
    def event_logger(event):
        level = event.get("log_level")
        failure = event.get("log_failure")

        if level == LogLevel.critical and failure:
            logger.error("Twisted: unhandled error in Deferred: {}"
                         .format(failure))
    return event_logger
