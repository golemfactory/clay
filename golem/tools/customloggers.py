from raven.handlers.logging import SentryHandler

DEFAULT_SENTRY_ENABLED = False


class SwitchedSentryHandler(SentryHandler):

    def __init__(self, *args, **kwargs):
        try:
            self.enabled = bool(kwargs.pop('enabled', DEFAULT_SENTRY_ENABLED))
        except Exception:   # pylint: disable=broad-except
            self.enabled = DEFAULT_SENTRY_ENABLED
        super().__init__(*args, **kwargs)

    def emit(self, record):
        if not self.enabled:
            return None
        return super().emit(record)

    def set_enabled(self, value):
        try:
            self.enabled = bool(value)
        except Exception:   # pylint: disable=broad-except
            self.enabled = DEFAULT_SENTRY_ENABLED
