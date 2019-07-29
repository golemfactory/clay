import logging
from raven.handlers.logging import SentryHandler

DEFAULT_SENTRY_ENABLED = False


class SwitchedSentryHandler(SentryHandler):

    def __init__(self, *args, **kwargs):
        try:
            self.enabled = bool(kwargs.pop('enabled', DEFAULT_SENTRY_ENABLED))
        except Exception:   # pylint: disable=broad-except
            self.enabled = DEFAULT_SENTRY_ENABLED
        self._user = {}
        super().__init__(*args, **kwargs)

    def emit(self, record):
        if not self.enabled:
            return None
        self.client.context.merge({'user': self._user})
        return super().emit(record)

    def update_user(self, **kwargs):
        self._user.update(kwargs)

    def set_version(self, version=None, env=None):
        if version is not None:
            self.client.release = version
        if env is not None:
            self.client.environment = env

    def set_enabled(self, value):
        try:
            self.enabled = bool(value)
        except Exception:   # pylint: disable=broad-except
            self.enabled = DEFAULT_SENTRY_ENABLED


class SentryMetricsFilter(logging.Filter):
    # pylint: disable=R0903
    def filter(self, record):
        return record.getMessage().startswith('METRIC')
