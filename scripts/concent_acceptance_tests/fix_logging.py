import logging

from ethereum import slogging


# Monkey patch for ethereum.slogging.
# SLogger aggressively mess up with python logger.
# This patch is to settle down this.
# It should be done before any SLogger is created.


orig_getLogger = slogging.SManager.getLogger


def monkey_patched_getLogger(*args, **kwargs):
    orig_class = logging.getLoggerClass()
    result = orig_getLogger(*args, **kwargs)
    logging.setLoggerClass(orig_class)
    return result


slogging.SManager.getLogger = monkey_patched_getLogger
