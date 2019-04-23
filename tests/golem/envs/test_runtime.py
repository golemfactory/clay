from logging import Logger
from unittest import TestCase
from unittest.mock import Mock, patch

from golem.envs import RuntimeStatus, Runtime


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


class TestWrapStatusChange(TestRuntime):

    def test_error(self):
        func = Mock(side_effect=ValueError)
        error_msg = "test error"
        wrapper = self.runtime._wrap_status_change(
            success_status=RuntimeStatus.RUNNING,
            error_msg=error_msg
        )
        wrapped = wrapper(func)

        with self.assertRaises(ValueError):
            wrapped()

        self.logger.exception.assert_called_once_with(error_msg)
        self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)

    def test_success(self):
        func = Mock()
        success_msg = "test success"
        wrapper = self.runtime._wrap_status_change(
            success_status=RuntimeStatus.RUNNING,
            success_msg=success_msg
        )
        wrapped = wrapper(func)

        wrapped()

        self.logger.info.assert_called_once_with(success_msg)
        self.assertEqual(self.runtime.status(), RuntimeStatus.RUNNING)
