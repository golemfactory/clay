from logging import Logger
from unittest import TestCase
from unittest.mock import Mock, patch

from dataclasses import dataclass

from twisted.internet import defer

from golem.envs import (
    EnvConfig,
    EnvEvent,
    EnvEventType,
    EnvironmentBase,
    EnvStatus,
    Prerequisites,
    delayed_config,
)


class TestEnvironmentBase(TestCase):

    @patch.object(EnvironmentBase, "__abstractmethods__", set())
    def setUp(self) -> None:
        self.logger = Mock(spec=Logger)
        # pylint: disable=abstract-class-instantiated
        self.env = EnvironmentBase(logger=self.logger)  # type: ignore


class TestEmitEvents(TestEnvironmentBase):

    @patch('golem.envs.deferToThread')
    def test_emit_event(self, defer):
        defer.side_effect = lambda f, *args, **kwargs: f(*args, **kwargs)
        enabled_listener1 = Mock()
        enabled_listener2 = Mock()
        disabled_listener = Mock()

        self.env.listen(EnvEventType.ENABLED, enabled_listener1)
        self.env.listen(EnvEventType.ENABLED, enabled_listener2)
        self.env.listen(EnvEventType.DISABLED, disabled_listener)

        event = EnvEvent(
            type=EnvEventType.ENABLED,
            details={"key": "value"}
        )

        self.env._emit_event(event.type, event.details)

        enabled_listener1.assert_called_once_with(event)
        enabled_listener2.assert_called_once_with(event)
        disabled_listener.assert_not_called()

    @patch('golem.envs.EnvironmentBase._emit_event')
    def test_env_enabled(self, emit):
        self.env._env_enabled()
        self.assertEqual(self.env.status(), EnvStatus.ENABLED)
        self.logger.info.assert_called_once_with('Environment enabled.')
        emit.assert_called_once_with(EnvEventType.ENABLED)

    @patch('golem.envs.EnvironmentBase._emit_event')
    def test_env_disabled(self, emit):
        self.env._status = EnvStatus.ENABLED
        self.env._env_disabled()
        self.assertEqual(self.env.status(), EnvStatus.DISABLED)
        self.logger.info.assert_called_once_with('Environment disabled.')
        emit.assert_called_once_with(EnvEventType.DISABLED)

    @patch('golem.envs.EnvironmentBase._emit_event')
    def test_config_updated(self, emit):
        config = Mock(spec=EnvConfig)
        self.env._config_updated(config)
        self.logger.info.assert_called_once_with('Configuration updated.')
        emit.assert_called_once_with(
            EnvEventType.CONFIG_UPDATED, {'config': config})

    @patch('golem.envs.EnvironmentBase._emit_event')
    def test_prerequisites_installed(self, emit):
        prereqs = Mock(spec=Prerequisites)
        self.env._prerequisites_installed(prereqs)
        self.logger.info.assert_called_once_with('Prerequisites installed.')
        emit.assert_called_once_with(
            EnvEventType.PREREQUISITES_INSTALLED,
            {'prerequisites': prereqs})

    @patch('golem.envs.EnvironmentBase._emit_event')
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


class TestListen(TestEnvironmentBase):

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


@dataclass
class MyConfig(EnvConfig):
    i: int

    def to_dict(self) -> dict:
        pass

    @staticmethod
    def from_dict(data):
        pass


@delayed_config
class MyEnv(EnvironmentBase):
    def __init__(self, config: MyConfig) -> None:
        super().__init__()
        self._config = config

    def update_config(self, config: EnvConfig) -> None:
        assert isinstance(config, MyConfig)
        self._logger.debug("dupa %r", self._event_listeners)
        if self._status != EnvStatus.DISABLED:
            raise ValueError
        self._config = config
        self._config_updated(config)

    def config(self) -> MyConfig:
        return self._config

    @classmethod
    def supported(cls):
        raise NotImplementedError

    def prepare(self):
        raise NotImplementedError

    def clean_up(self):
        raise NotImplementedError

    def run_benchmark(self):
        raise NotImplementedError

    def parse_prerequisites(self, prerequisites_dict):
        raise NotImplementedError

    def install_prerequisites(self, prerequisites):
        raise NotImplementedError

    def parse_config(self, config_dict):
        raise NotImplementedError

    def supported_usage_counters(self):
        raise NotImplementedError

    def runtime(self, payload, config=None):
        raise NotImplementedError


def execute(f, *args, **kwargs):
    try:
        return defer.succeed(f(*args, **kwargs))
    except Exception as exc:  # pylint: disable=broad-except
        return defer.fail(exc)


@patch('golem.envs.deferToThread', execute)
class TestDelayedConfig(TestCase):

    def setUp(self) -> None:
        config = MyConfig(i=1)
        self.env = MyEnv(config)

    def test_update_config_when_disabled(self):
        self.env.update_config(MyConfig(i=2))
        self.assertEqual(self.env.config().i, 2)

    def test_update_config_when_enabled(self):
        self.env._env_enabled()
        self.env.update_config(MyConfig(i=2))
        self.assertEqual(self.env.config().i, 1)
        self.env._env_disabled()
        self.assertEqual(self.env.config().i, 2)
