from logging import Logger
from unittest import TestCase
from unittest.mock import Mock, patch

from golem.envs import Environment, EnvEvent, EnvEventType, EnvConfig, \
    Prerequisites, EnvStatus


class TestEnvironment(TestCase):

    @patch.object(Environment, "__abstractmethods__", set())
    def setUp(self) -> None:
        self.logger = Mock(spec=Logger)
        # pylint: disable=abstract-class-instantiated
        self.env = Environment(logger=self.logger)  # type: ignore


class TestEmitEvents(TestEnvironment):

    @patch('golem.envs.deferToThread')
    def test_emit_event(self, defer):
        defer.side_effect = lambda f, *args, **kwargs: f(*args, **kwargs)
        metadata = Mock(id="env_id")
        with patch.object(self.env, 'metadata', return_value=metadata):
            enabled_listener1 = Mock()
            enabled_listener2 = Mock()
            disabled_listener = Mock()

            self.env.listen(EnvEventType.ENABLED, enabled_listener1)
            self.env.listen(EnvEventType.ENABLED, enabled_listener2)
            self.env.listen(EnvEventType.DISABLED, disabled_listener)

            event = EnvEvent(
                env_id="env_id",
                type=EnvEventType.ENABLED,
                details={"key": "value"}
            )

            self.env._emit_event(event.type, event.details)

            enabled_listener1.assert_called_once_with(event)
            enabled_listener2.assert_called_once_with(event)
            disabled_listener.assert_not_called()

    @patch('golem.envs.Environment._emit_event')
    def test_env_enabled(self, emit):
        self.env._env_enabled()
        self.assertEqual(self.env.status(), EnvStatus.ENABLED)
        self.logger.info.assert_called_once_with('Environment enabled.')
        emit.assert_called_once_with(EnvEventType.ENABLED)

    @patch('golem.envs.Environment._emit_event')
    def test_env_disabled(self, emit):
        self.env._status = EnvStatus.ENABLED
        self.env._env_disabled()
        self.assertEqual(self.env.status(), EnvStatus.DISABLED)
        self.logger.info.assert_called_once_with('Environment disabled.')
        emit.assert_called_once_with(EnvEventType.DISABLED)

    @patch('golem.envs.Environment._emit_event')
    def test_config_updated(self, emit):
        config = Mock(spec=EnvConfig)
        self.env._config_updated(config)
        self.logger.info.assert_called_once_with('Configuration updated.')
        emit.assert_called_once_with(
            EnvEventType.CONFIG_UPDATED, {'config': config})

    @patch('golem.envs.Environment._emit_event')
    def test_prerequisites_installed(self, emit):
        prereqs = Mock(spec=Prerequisites)
        self.env._prerequisites_installed(prereqs)
        self.logger.info.assert_called_once_with('Prerequisites installed.')
        emit.assert_called_once_with(
            EnvEventType.PREREQUISITES_INSTALLED,
            {'prerequisites': prereqs})

    @patch('golem.envs.Environment._emit_event')
    def test_error_occurred(self, emit):
        error = RuntimeError("test")
        message = "error message"
        self.env._error_occurred(error, message)
        self.assertEqual(self.env.status(), EnvStatus.ERROR)
        self.logger.error.assert_called_once_with(message, exc_info=error)
        emit.assert_called_once_with(
            EnvEventType.ERROR_OCCURRED, {
                'error': error,
                'message': message
            })


class TestListen(TestEnvironment):

    def test_single_listener(self):
        listener = Mock()
        self.env.listen(EnvEventType.ENABLED, listener)
        self.assertEqual(self.env._event_listeners, {
            EnvEventType.ENABLED: {listener}
        })

    def test_multiple_listeners(self):
        enabled_listener1 = Mock()
        enabled_listener2 = Mock()
        disabled_listener = Mock()

        self.env.listen(EnvEventType.ENABLED, enabled_listener1)
        self.env.listen(EnvEventType.ENABLED, enabled_listener2)
        self.env.listen(EnvEventType.DISABLED, disabled_listener)

        self.assertEqual(self.env._event_listeners, {
            EnvEventType.ENABLED: {enabled_listener1, enabled_listener2},
            EnvEventType.DISABLED: {disabled_listener}
        })

    def test_re_register(self):
        listener = Mock()
        self.env.listen(EnvEventType.ERROR_OCCURRED, listener)
        self.env.listen(EnvEventType.ERROR_OCCURRED, listener)
        self.assertEqual(self.env._event_listeners, {
            EnvEventType.ERROR_OCCURRED: {listener}
        })
