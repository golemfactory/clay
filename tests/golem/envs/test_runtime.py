from logging import Logger
from unittest import TestCase
from unittest.mock import Mock, patch

from golem.envs import RuntimeStatus, Runtime, RuntimeEventType, RuntimeEvent


class TestRuntime(TestCase):

    @patch.object(Runtime, "__abstractmethods__", set())
    def setUp(self) -> None:
        self.logger = Mock(spec=Logger)
        # pylint: disable=abstract-class-instantiated
        self.runtime = Runtime(logger=self.logger)  # type: ignore


class TestChangeStatus(TestRuntime):

    def test_wrong_single_status(self):
        with self.assertRaises(ValueError):
            self.runtime._change_status(
                from_status=RuntimeStatus.STOPPED,
                to_status=RuntimeStatus.RUNNING)

    def test_wrong_multiple_statuses(self):
        with self.assertRaises(ValueError):
            self.runtime._change_status(
                from_status=[RuntimeStatus.STOPPED, RuntimeStatus.FAILURE],
                to_status=RuntimeStatus.RUNNING)

    def test_ok(self):
        self.runtime._change_status(
            from_status=RuntimeStatus.CREATED,
            to_status=RuntimeStatus.RUNNING)
        self.assertEqual(self.runtime.status(), RuntimeStatus.RUNNING)


class TestEmitEvents(TestRuntime):

    @patch('golem.envs.deferToThread')
    def test_emit_event(self, defer):
        defer.side_effect = lambda f, *args, **kwargs: f(*args, **kwargs)

        started_listener1 = Mock()
        started_listener2 = Mock()
        stopped_listener = Mock()

        self.runtime.listen(RuntimeEventType.STARTED, started_listener1)
        self.runtime.listen(RuntimeEventType.STARTED, started_listener2)
        self.runtime.listen(RuntimeEventType.STOPPED, stopped_listener)

        event = RuntimeEvent(
            type=RuntimeEventType.STARTED,
            details={"key": "value"}
        )

        self.runtime._emit_event(event.type, event.details)

        started_listener1.assert_called_once_with(event)
        started_listener2.assert_called_once_with(event)
        stopped_listener.assert_not_called()

    @patch('golem.envs.Runtime._emit_event')
    def test_prepared(self, emit):
        self.runtime._prepared()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARED)
        self.logger.info.assert_called_once_with('Runtime prepared.')
        emit.assert_called_once_with(RuntimeEventType.PREPARED)

    @patch('golem.envs.Runtime._emit_event')
    def test_started(self, emit):
        self.runtime._started()
        self.assertEqual(self.runtime.status(), RuntimeStatus.RUNNING)
        self.logger.info.assert_called_once_with('Runtime started.')
        emit.assert_called_once_with(RuntimeEventType.STARTED)

    @patch('golem.envs.Runtime._emit_event')
    def test_stopped(self, emit):
        self.runtime._stopped()
        self.assertEqual(self.runtime.status(), RuntimeStatus.STOPPED)
        self.logger.info.assert_called_once_with('Runtime stopped.')
        emit.assert_called_once_with(RuntimeEventType.STOPPED)

    @patch('golem.envs.Runtime._emit_event')
    def test_torn_down(self, emit):
        self.runtime._torn_down()
        self.assertEqual(self.runtime.status(), RuntimeStatus.TORN_DOWN)
        self.logger.info.assert_called_once_with('Runtime torn down.')
        emit.assert_called_once_with(RuntimeEventType.TORN_DOWN)

    @patch('golem.envs.Runtime._emit_event')
    def test_error_occurred(self, emit):
        error = RuntimeError("test")
        message = "error message"
        self.runtime._error_occurred(error, message)
        self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
        self.logger.error.assert_called_once_with(message, exc_info=error)
        emit.assert_called_once_with(
            RuntimeEventType.ERROR_OCCURRED, {
                'error': error,
                'message': message
            })
