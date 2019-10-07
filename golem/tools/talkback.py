import logging
from typing import Optional, Dict, cast

logger = logging.getLogger(__name__)

_sentry_user: Dict[str, str] = dict()


def user() -> Optional[Dict[str, str]]:
    return None if 'env' not in _sentry_user else _sentry_user.copy()


def update_sentry_user(node_id: str, node_name: Optional[str] = None):
    from golem.tools.customloggers import SwitchedSentryHandler
    logger_root = logging.getLogger()
    _sentry_user['id'] = node_id
    if node_name is not None:
        _sentry_user['nodeName'] = node_name

    for handler in [
            cast(SwitchedSentryHandler, h)
            for h in logger_root.handlers
            if isinstance(h, SwitchedSentryHandler)
    ]:
        handler.update_user(id=node_id, node_name=node_name)


def enable_sentry_logger(talkback_value: bool):
    from golem.tools.customloggers import SwitchedSentryHandler
    logger_root = logging.getLogger()
    try:
        import golem
        from golem.config.active import EthereumConfig

        is_mainnet = EthereumConfig().IS_MAINNET

        env = 'mainnet' if is_mainnet else 'testnet'

        if talkback_value:
            _sentry_user["env"] = env
            _sentry_user["golemVersion"] = golem.__version__

        sentry_handler = [
            h for h in logger_root.handlers
            if isinstance(h, SwitchedSentryHandler)
        ]
        for handler in sentry_handler:
            msg_part = 'Enabling' if talkback_value else 'Disabling'
            logger.debug('%s talkback %r service', msg_part, handler.name)
            handler.set_enabled(talkback_value)
            handler.set_version(golem.__version__, env)
    except Exception as e:  # pylint: disable=broad-except
        msg_part = 'enable' if talkback_value else 'disable'
        logger.error('Cannot %s talkback. Error was: %s', msg_part, str(e))
