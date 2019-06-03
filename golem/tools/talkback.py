import logging

logger = logging.getLogger(__name__)


def enable_sentry_logger(value):
    talkback_value = bool(value)
    logger_root = logging.getLogger()
    try:
        sentry_handler = [h for h in logger_root.handlers if h.name == 'sentry'
                          or h.name == 'sentry-metrics']
        for handler in sentry_handler:
            msg_part = 'Enabling' if talkback_value else 'Disabling'
            logger.debug('%s talkback %r service', msg_part, handler.name)
            handler.set_enabled(talkback_value)
    except Exception as e:  # pylint: disable=broad-except
        msg_part = 'enable' if talkback_value else 'disable'
        logger.error(
            'Cannot %s talkback. Error was: %s', msg_part, str(e))
