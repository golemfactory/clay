from socket import socket
from threading import RLock, Thread
from unittest.mock import Mock, patch as _patch, call

import pytest
from docker.errors import APIError
from twisted.trial.unittest import TestCase

from golem.envs import RuntimeStatus
from golem.envs.docker import DockerPayload, DockerBind
from golem.envs.docker.cpu import DockerCPURuntime, DockerOutput, DockerInput


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
            binds=[Mock(spec=DockerBind)],
            env={'key': 'value'},
            user='user',
            work_dir='/test'
        )
        host_config = {'memory': '1234m'}
        runtime = DockerCPURuntime(payload, host_config)

        local_client().create_container_config.assert_called_once_with(
            image='repo/img:1.0',
            command='cmd',
            volumes=[payload.binds[0].target],
            environment={'key': 'value'},
            user='user',
            working_dir='/test',
            host_config=host_config,
            stdin_open=True,
        )
        self.assertEqual(runtime.status(), RuntimeStatus.CREATED)
        self.assertIsNone(runtime._container_id)
        self.assertIsNone(runtime._stdin_socket)
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

        log_warning_patch = patch('logger.warning')
        log_error_patch = patch('logger.error')
        log_exception_patch = patch('logger.exception')
        self.log_warning = log_warning_patch.start()
        self.log_error = log_error_patch.start()
        self.log_exception = log_exception_patch.start()
        self.addCleanup(log_warning_patch.stop)
        self.addCleanup(log_error_patch.stop)
        self.addCleanup(log_exception_patch.stop)

    def _generic_test_invalid_status(self, method, valid_statuses):
        def _test(status):
            with self.runtime._status_lock:
                self.runtime._status = status

            with self.assertRaises(ValueError):
                method()

        for status in set(RuntimeStatus) - valid_statuses:
            _test(status)


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
        self.log_exception.assert_called_once()

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
        self.log_error.assert_called_once()


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

    def test_create_error(self):
        self.client.create_container_from_config.side_effect = APIError("error")

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.assertIsNone(self.runtime._stdin_socket)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_not_called()
            self.log_exception.assert_called_once()
        deferred.addCallback(_check)

        return deferred

    def test_invalid_container_id(self):
        self.client.create_container_from_config.return_value = {"Id": None}

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, AssertionError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.assertIsNone(self.runtime._stdin_socket)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_not_called()
            self.log_exception.assert_called_once()
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
            self.assertEqual(
                self.runtime._stdin_socket,
                self.client.attach_socket.return_value)
            self.assertEqual(self.runtime._container_id, "Id")
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_called_once_with(
                "Id", params={"stdin": True, "stream": True})
            self.log_exception.assert_not_called()

            warning_calls = self.log_warning.call_args_list
            self.assertEqual(len(warning_calls), 2)
            self.assertIn("foo", warning_calls[0][0])
            self.assertIn("bar", warning_calls[1][0])

        deferred.addCallback(_check)

        return deferred

    def test_attach_socket_error(self):
        self.client.create_container_from_config.return_value = {"Id": "Id"}
        self.client.attach_socket.side_effect = APIError("")

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.assertIsNone(self.runtime._stdin_socket)
            self.assertEqual(self.runtime._container_id, "Id")
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_called_once_with(
                "Id", params={"stdin": True, "stream": True})
            self.log_exception.assert_called_once()
            self.log_warning.assert_not_called()

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        self.client.create_container_from_config.return_value = {"Id": "Id"}

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARED)
            self.assertEqual(
                self.runtime._stdin_socket,
                self.client.attach_socket.return_value)
            self.assertEqual(self.runtime._container_id, "Id")
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_called_once_with(
                "Id", params={"stdin": True, "stream": True})
            self.log_exception.assert_not_called()
            self.log_warning.assert_not_called()

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
        self.runtime._stdin_socket = Mock(spec=socket)
        self.client.remove_container.side_effect = APIError("error")

        deferred = self.runtime.cleanup()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.client.remove_container.assert_called_once_with("Id")
            self.runtime._stdin_socket.close.assert_called_once()
            self.log_exception.assert_called_once()

        deferred.addCallback(_check)

        return deferred

    def test_no_socket(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.STOPPED
        self.runtime._container_id = "Id"

        deferred = self.runtime.cleanup()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.TORN_DOWN)
            self.client.remove_container.assert_called_once_with("Id")
            self.log_exception.assert_not_called()

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.STOPPED
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=socket)

        deferred = self.runtime.cleanup()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.TORN_DOWN)
            self.client.remove_container.assert_called_once_with("Id")
            self.runtime._stdin_socket.close.assert_called_once()
            self.log_exception.assert_not_called()

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
            self.log_exception.assert_called_once()
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
            self.log_exception.assert_not_called()

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
        self.runtime._stdin_socket = Mock(spec=socket)
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = False
        self.client.stop.side_effect = APIError("error")

        deferred = self.assertFailure(self.runtime.stop(), APIError)

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.FAILURE)
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.runtime._stdin_socket.close.assert_called_once()
            self.log_exception.assert_called_once()
            self.log_warning.assert_not_called()

        deferred.addCallback(_check)

        return deferred

    def test_failed_to_join_status_update_thread(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=socket)
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = True

        deferred = self.runtime.stop()

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.STOPPED)
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.runtime._stdin_socket.close.assert_called_once()
            self.log_exception.assert_not_called()
            self.log_warning.assert_called_once()

        deferred.addCallback(_check)

        return deferred

    def test_ok(self):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=socket)
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = False

        deferred = self.runtime.stop()

        def _check(_):
            self.assertEqual(self.runtime.status(), RuntimeStatus.STOPPED)
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.runtime._stdin_socket.close.assert_called_once()
            self.log_exception.assert_not_called()
            self.log_warning.assert_not_called()

        deferred.addCallback(_check)

        return deferred


class TestStdinSocket(TestDockerCPURuntime):

    def _patch_socket(self):
        self.runtime._stdin_lock = RLock()
        self.runtime._stdin_socket = Mock(spec=socket)


class TestWriteStdin(TestDockerCPURuntime):

    def test_no_socket(self):
        with self.assertRaises(AssertionError):
            self.runtime._write_stdin(b"test")

    def test_ok(self):
        self.runtime._stdin_lock = RLock()
        self.runtime._stdin_socket = Mock(spec=socket)
        self.runtime._stdin_socket.sendall.side_effect = \
            lambda _: self.assertTrue(self.runtime._stdin_lock._is_owned())

        self.runtime._write_stdin(b"test")
        self.runtime._stdin_socket.sendall.assert_called_once_with(b"test")


class TestCloseStdin(TestDockerCPURuntime):

    def test_no_socket(self):
        with self.assertRaises(AssertionError):
            self.runtime._close_stdin()

    def test_ok(self):
        self.runtime._stdin_lock = RLock()
        self.runtime._stdin_socket = Mock(spec=socket)
        self.runtime._stdin_socket.shutdown.side_effect = \
            lambda: self.assertTrue(self.runtime._stdin_lock._is_owned())
        self.runtime._stdin_socket.close.side_effect = \
            lambda: self.assertTrue(self.runtime._stdin_lock._is_owned())

        self.runtime._close_stdin()
        self.runtime._stdin_socket.shutdown.assert_called_once()
        self.runtime._stdin_socket.close.assert_called_once()


class TestStdin(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.stdin,
            valid_statuses={
                RuntimeStatus.PREPARED,
                RuntimeStatus.STARTING,
                RuntimeStatus.RUNNING}
        )

    @patch_runtime('_close_stdin')
    @patch_runtime('_write_stdin')
    def test_ok(self, write, close):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING
        self.runtime._stdin_socket = Mock(spec=socket)

        result = self.runtime.stdin(encoding="utf-8")
        self.assertIsInstance(result, DockerInput)
        self.assertEqual(result._write, write)
        self.assertEqual(result._close, close)
        self.assertEqual(result._encoding, "utf-8")


class TestStdout(TestDockerCPURuntime):

    @patch_runtime('_get_output', side_effect=ValueError)
    def test_error(self, _):
        with self.assertRaises(ValueError):
            self.runtime.stdout()

    @patch_runtime('_get_output')
    def test_ok(self, get_output):
        result = self.runtime.stdout(encoding="utf-8")
        get_output.assert_called_once_with(stdout=True, encoding="utf-8")
        self.assertEqual(result, get_output.return_value)


class TestStderr(TestDockerCPURuntime):

    @patch_runtime('_get_output', side_effect=ValueError)
    def test_error(self, _):
        with self.assertRaises(ValueError):
            self.runtime.stderr()

    @patch_runtime('_get_output')
    def test_ok(self, get_output):
        result = self.runtime.stderr(encoding="utf-8")
        get_output.assert_called_once_with(stderr=True, encoding="utf-8")
        self.assertEqual(result, get_output.return_value)


class TestGetOutput(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime._get_output,
            valid_statuses={
                RuntimeStatus.PREPARED,
                RuntimeStatus.STARTING,
                RuntimeStatus.RUNNING,
                RuntimeStatus.STOPPED,
                RuntimeStatus.FAILURE
            }
        )

    @patch_runtime('_update_status')
    @patch_runtime('_get_raw_output')
    def test_running(self, get_raw_output, update_status):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING

        result = self.runtime._get_output(stdout=True, encoding="utf-8")
        get_raw_output.assert_called_once_with(stdout=True, stream=True)
        update_status.assert_called_once()
        self.assertIsInstance(result, DockerOutput)
        self.assertEqual(result._raw_output, get_raw_output.return_value)
        self.assertEqual(result._encoding, "utf-8")

    @patch_runtime('_update_status')
    @patch_runtime('_get_raw_output')
    def test_stopped(self, get_raw_output, update_status):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.STOPPED

        result = self.runtime._get_output(stdout=True, encoding="utf-8")
        get_raw_output.assert_called_once_with(stdout=True, stream=False)
        update_status.assert_called_once()
        self.assertIsInstance(result, DockerOutput)
        self.assertEqual(result._raw_output, get_raw_output.return_value)
        self.assertEqual(result._encoding, "utf-8")

    @patch_runtime('_update_status')
    @patch_runtime('_get_raw_output')
    def test_stopped_in_the_meantime(self, get_raw_output, update_status):
        with self.runtime._status_lock:
            self.runtime._status = RuntimeStatus.RUNNING

        def _update_status():
            with self.runtime._status_lock:
                self.runtime._status = RuntimeStatus.STOPPED
        update_status.side_effect = _update_status
        raw_output = Mock()
        get_raw_output.side_effect = [None, raw_output]

        result = self.runtime._get_output(stdout=True, encoding="utf-8")
        get_raw_output.assert_has_calls([
            call(stdout=True, stream=True),
            call(stdout=True, stream=False)])
        update_status.assert_called_once()
        self.assertIsInstance(result, DockerOutput)
        self.assertEqual(result._raw_output, raw_output)
        self.assertEqual(result._encoding, "utf-8")


class TestGetRawOutput(TestDockerCPURuntime):

    def setUp(self) -> None:
        super().setUp()
        self.runtime._container_id = "container_id"

    def test_no_arguments(self):
        with self.assertRaises(AssertionError):
            self.runtime._get_raw_output()

    def test_container_id_missing(self):
        self.runtime._container_id = None
        with self.assertRaises(AssertionError):
            self.runtime._get_raw_output(stdout=True)

    def test_client_error(self):
        self.client.attach.side_effect = APIError("")
        result = self.runtime._get_raw_output(stdout=True)
        self.assertEqual(result, [])
        self.log_exception.assert_called_once()

    def test_stdout_stream(self):
        result = self.runtime._get_raw_output(stdout=True, stream=True)
        self.assertEqual(result, self.client.attach.return_value)
        self.client.attach.assert_called_once_with(
            container=self.runtime._container_id,
            stdout=True,
            stderr=False,
            logs=True,
            stream=True
        )

    def test_stderr_non_stream(self):
        result = self.runtime._get_raw_output(stderr=True, stream=False)
        self.assertEqual(result, [self.client.attach.return_value])
        self.client.attach.assert_called_once_with(
            container=self.runtime._container_id,
            stdout=False,
            stderr=True,
            logs=True,
            stream=False
        )
