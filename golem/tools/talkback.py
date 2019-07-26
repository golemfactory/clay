import logging
from typing import Optional

logger = logging.getLogger(__name__)

__sentry_user = dict()


def user() -> dict:
    return __sentry_user.copy()


def update_sentry_user(id: str, node_name: Optional[str] = None):
    logger_root = logging.getLogger()
    __sentry_user["id"] = id
    __sentry_user["nodeName"] = node_name

    for handler in [h for h in logger_root.handlers if h.name == 'sentry'
            or h.name == 'sentry-metrics']:
        handler.update_user(id=id, node_name=node_name)


def enable_sentry_logger(value):
    talkback_value = bool(value)
    logger_root = logging.getLogger()
    try:
        import golem
        from golem.config.active import EthereumConfig

        is_mainnet = EthereumConfig().IS_MAINNET
        env = 'mainnet' if is_mainnet else 'testnet'

        __sentry_user["env"] = env
        __sentry_user["golemVersion"] = golem.__version__

        sentry_handler = [h for h in logger_root.handlers if h.name == 'sentry'
                          or h.name == 'sentry-metrics']
        for handler in sentry_handler:
            msg_part = 'Enabling' if talkback_value else 'Disabling'
            logger.debug('%s talkback %r service', msg_part, handler.name)
            handler.set_enabled(talkback_value)
            handler.set_version(golem.__version__, env)
    except Exception as e:  # pylint: disable=broad-except
        msg_part = 'enable' if talkback_value else 'disable'
        logger.error(
            'Cannot %s talkback. Error was: %s', msg_part, str(e))
