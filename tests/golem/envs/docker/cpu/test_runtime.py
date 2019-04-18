from threading import RLock, Thread
from unittest.mock import Mock, patch as _patch

import pytest
from docker.errors import APIError
from twisted.trial.unittest import TestCase

from golem.envs import RuntimeStatus
from golem.envs.docker import DockerPayload, DockerBind
from golem.envs.docker.cpu import DockerCPURuntime


def patch(name: str, *args, **kwargs):
    return _patch(f'golem.envs.docker.cpu.{name}', *args, **kwargs)


def patch_runtime(name: str, *args, **kwargs):
    return patch(f'DockerCPURuntime.{name}', *args, **kwargs)


class TestInit(TestCase):

    @patch('local_client')
    def test_init(self, local_client):
        payload = DockerPayload(
            image='repo/img',
            tag='1.0',
            command='cmd',
            args=['arg1', 'arg2'],
            binds=[Mock(spec=DockerBind)],
            env={'key': 'value'},
            user='user',
            work_dir='/test'
        )
        host_config = {'memory': '1234m'}
        runtime = DockerCPURuntime(payload, host_config)

        local_client().create_container_config.assert_called_once_with(
            image='repo/img:1.0',
            command=['cmd', 'arg1', 'arg2'],
            volumes=[payload.binds[0].target],
            environment={'key': 'value'},
            user='user',
            working_dir='/test',
            host_config=host_config
        )
        self.assertEqual(runtime.status(), RuntimeStatus.CREATED)
        self.assertIsNone(runtime._container_id)
        self.assertEqual(
            runtime._container_config,
            local_client().create_container_config())


class TestDockerCPURuntime(TestCase):

    def setUp(self) -> None:
        super().setUp()

        client_patch = patch('local_client')
        self.client = client_patch.start()()
        self.addCleanup(client_patch.stop)

        payload = DockerPayload(
            image='repo/img',
            tag='1.0',
            args=[],
            binds=[],
            env={}
        )
        self.runtime = DockerCPURuntime(payload, {})
        self.container_config = self.client.create_container_config()

        # We want to make sure that status is being set and read using lock.
        # RLock enables us to check whether it's owned by the current thread.
        self.runtime._status_lock = RLock()  # type: ignore

        def _getattribute(obj, item):
            if item == "_status" and not self.runtime._status_lock._is_owned():
                self.fail("Status read without lock")
            return object.__getattribute__(obj, item)

        def _setattr(obj, name, value):
            if name == "_status" and not self.runtime._status_lock._is_owned():
                self.fail("Status write without lock")
            return object.__setattr__(obj, name, value)

        get_patch = patch_runtime('__getattribute__', _getattribute)
        get_patch.start()
        self.addCleanup(get_patch.stop)

        set_patch = patch_runtime('__setattr__', _setattr)
        set_patch.start()
        self.addCleanup(set_patch.stop)

        logger_patch = patch('logger')
        self.logger = logger_patch.start()
        self.addCleanup(logger_patch.stop)

    def _generic_test_invalid_status(self, method, valid_statuses):
        def _test(status):
            with self.runtime._status_lock:
                self.runtime._status = status

            with self.assertRaises(ValueError):
                method()

        for status in set(RuntimeStatus) - valid_statuses:
            _test(status)


class TestChangeStatus(TestDockerCPURuntime):

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


class TestWrapStatusChange(TestDockerCPURuntime):

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


class TestInspectContainer(TestDockerCPURuntime):

    def test_no_container_id(self):
        with self.assertRaises(AssertionError):
            self.runtime._inspect_container()

    def test_ok(self):
        self.runtime._container_id = "container_id"
        self.client.inspect_container.return_value = {
            "State": {
                "Status": "running",
                "ExitCode": 0
            }
        }

        status, exit_code = self.runtime._inspect_container()

        self.client.inspect_container.assert_called_once_with("container_id")
        self.assertEqual(status, "running")
        self.assertEqual(exit_code, 0)


class TestUpdateStatus(TestDockerCPURuntime):

    def test_status_not_running(self):
        self.assertFalse(self.runtime._update_status())
        self.assertEqual(self.runtime.status(), RuntimeStatus.CREATED)

    def _generic_test(self, exp_status, inspect_error=None,
                      inspect_result=None):

        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING

        with patch_runtime('_inspect_container',
                           side_effect=inspect_error,
                           return_value=inspect_result):
            self.runtime._update_status()
            self.assertEqual(self.runtime.status(), exp_status)

    def test_docker_api_error(self):
        self._generic_test(
            exp_status=RuntimeStatus.FAILURE,
            inspect_error=APIError("error"))
        self.logger.exception.assert_called_once()

    def test_container_running(self):
        self._generic_test(
            exp_status=RuntimeStatus.RUNNING,
            inspect_result=("running", 0))

    def test_container_exited_ok(self):
        self._generic_test(
            exp_status=RuntimeStatus.STOPPED,
            inspect_result=("exited", 0))

    def test_container_exited_error(self):
        self._generic_test(
            exp_status=RuntimeStatus.FAILURE,
            inspect_result=("exited", -1234))

    def test_container_dead(self):
        self._generic_test(
            exp_status=RuntimeStatus.FAILURE,
            inspect_result=("dead", -1234))

    def test_container_unexpected_status(self):
        self._generic_test(
            exp_status=RuntimeStatus.FAILURE,
            inspect_result=("(╯°□°)╯︵ ┻━┻", 0))
        self.logger.error.assert_called_once()


class TestUpdateStatusLoop(TestDockerCPURuntime):

    # Timeout not to enter an infinite loop if there's a bug in the method
    @pytest.mark.timeout(0.1)
    @patch('sleep')
    @patch_runtime('_update_status')
    def test_not_running(self, update_status, sleep):
        self.runtime._update_status_loop()
        update_status.assert_not_called()
        sleep.assert_not_called()

    # Timeout not to enter an infinite loop if there's a bug in the method
    @pytest.mark.timeout(0.1)
    @patch('sleep')
    @patch_runtime('_update_status')
    def test_updated(self, update_status, sleep):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING

        def _update_status():
            with self.runtime._status_lock:
                self.runtime._status = RuntimeStatus.STOPPED
        update_status.side_effect = _update_status

        self.runtime._update_status_loop()
        update_status.assert_called_once()
        sleep.assert_called_once_with(DockerCPURuntime.STATUS_UPDATE_INTERVAL)


class TestPrepare(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.prepare,
            valid_statuses={RuntimeStatus.CREATED})

    def test_client_error(self):
        self.client.create_container_from_config.side_effect = APIError("error")

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.logger.exception.assert_called_once()
        deferred.addCallback(_check)

        return deferred

    def test_invalid_container_id(self):
        self.client.create_container_from_config.return_value = {"Id": None}

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, AssertionError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.logger.exception.assert_called_once()
        deferred.addCallback(_check)

        return deferred

    def test_warnings(self):
        self.client.create_container_from_config.return_value = {
            "Id": "Id",
            "Warnings": ["foo", "bar"]
        }

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARED)
            self.assertEqual(self.runtime._container_id, "Id")
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.logger.exception.assert_not_called()

            warning_calls = self.logger.warning.call_args_list
            self.assertEqual(len(warning_calls), 2)
            self.assertIn("foo", warning_calls[0][0])
            self.assertIn("bar", warning_calls[1][0])

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        self.client.create_container_from_config.return_value = {"Id": "Id"}

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARED)
            self.assertEqual(self.runtime._container_id, "Id")
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.logger.exception.assert_not_called()
            self.logger.warning.assert_not_called()

        deferred.addCallback(_check)

        return deferred


class TestCleanup(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.cleanup,
            valid_statuses={RuntimeStatus.STOPPED, RuntimeStatus.FAILURE})

    def test_client_error(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.STOPPED
        self.runtime._container_id = "Id"
        self.client.remove_container.side_effect = APIError("error")

        deferred = self.runtime.cleanup()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.client.remove_container.assert_called_once_with("Id")
            self.logger.exception.assert_called_once()

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.STOPPED
        self.runtime._container_id = "Id"

        deferred = self.runtime.cleanup()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.TORN_DOWN)
            self.client.remove_container.assert_called_once_with("Id")
            self.logger.exception.assert_not_called()

        deferred.addCallback(_check)

        return deferred


class TestStart(TestDockerCPURuntime):

    def setUp(self):
        super().setUp()
        loop_patch = patch_runtime('_update_status_loop')
        self.update_status_loop = loop_patch.start()
        self.addCleanup(loop_patch.stop)

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.start,
            valid_statuses={RuntimeStatus.PREPARED})

    def test_client_error(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.PREPARED
        self.runtime._container_id = "Id"
        self.client.start.side_effect = APIError("error")

        deferred = self.runtime.start()
        self.assertEqual(self.runtime.status(), RuntimeStatus.STARTING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.assertIsNone(self.runtime._status_update_thread)
            self.client.start.assert_called_once_with("Id")
            self.logger.exception.assert_called_once()
            self.update_status_loop.assert_not_called()

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.PREPARED
        self.runtime._container_id = "Id"

        deferred = self.runtime.start()
        self.assertEqual(self.runtime.status(), RuntimeStatus.STARTING)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.RUNNING)
            self.client.start.assert_called_once_with("Id")
            self.logger.exception.assert_not_called()

            self.assertIsInstance(self.runtime._status_update_thread, Thread)
            self.runtime._status_update_thread.join(0.1)
            self.update_status_loop.assert_called_once()

        deferred.addCallback(_check)

        return deferred


class TestStop(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.stop,
            valid_statuses={RuntimeStatus.RUNNING})

    def test_client_error(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING
        self.runtime._container_id = "Id"
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.client.stop.side_effect = APIError("error")

        deferred = self.assertFailure(self.runtime.stop(), APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_not_called()
            self.logger.exception.assert_called_once()
            self.logger.warning.assert_not_called()

        deferred.addCallback(_check)

        return deferred

    def test_failed_to_join_status_update_thread(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING
        self.runtime._container_id = "Id"
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = True

        deferred = self.runtime.stop()

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.STOPPED)
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.logger.exception.assert_not_called()
            self.logger.warning.assert_called_once()

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING
        self.runtime._container_id = "Id"
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = False

        deferred = self.runtime.stop()

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.STOPPED)
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.logger.exception.assert_not_called()
            self.logger.warning.assert_not_called()

        deferred.addCallback(_check)

        return deferred
