from threading import Thread
from unittest.mock import Mock, patch as _patch, call, ANY

import pytest
from docker.errors import APIError
from twisted.trial.unittest import TestCase

from golem.envs import RuntimeStatus
from golem.envs.docker import DockerPayload
from golem.envs.docker.cpu import DockerCPURuntime, DockerOutput, DockerInput, \
    InputSocket


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
            env={'key': 'value'},
            user='user',
            work_dir='/test'
        )
        host_config = {'memory': '1234m'}
        volumes = ['/test']
        runtime = DockerCPURuntime(payload, host_config, volumes)

        local_client().create_container_config.assert_called_once_with(
            image='repo/img:1.0',
            command='cmd',
            volumes=volumes,
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

        self.logger = self._patch_async('logger')
        self.client = self._patch_async('local_client').return_value
        self.container_config = self.client.create_container_config()

        payload = DockerPayload(
            image='repo/img',
            tag='1.0',
            env={}
        )

        self.runtime = DockerCPURuntime(payload, {}, None)
        self.container_config = self.client.create_container_config()

        # We want to make sure that status is being set and read using lock.

        def _getattribute(obj, item):
            if item == "_status" and not self.runtime._status_lock._is_owned():
                self.fail("Status read without lock")
            return object.__getattribute__(obj, item)

        def _setattr(obj, name, value):
            if name == "_status" and not self.runtime._status_lock._is_owned():
                self.fail("Status write without lock")
            return object.__setattr__(obj, name, value)

        self._patch_runtime_async('__getattribute__', _getattribute)
        self._patch_runtime_async('__setattr__', _setattr)

    def _generic_test_invalid_status(self, method, valid_statuses):
        def _test(status):
            self.runtime._set_status(status)
            with self.assertRaises(ValueError):
                method()

        for status in set(RuntimeStatus) - valid_statuses:
            _test(status)

    def _patch_async(self, name, *args, **kwargs):
        patcher = patch(name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _patch_runtime_async(self, name, *args, **kwargs):
        patcher = patch_runtime(name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()


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

    def _update_status(self, inspect_error=None, inspect_result=None):
        self.runtime._set_status(RuntimeStatus.RUNNING)
        with patch_runtime('_inspect_container',
                           side_effect=inspect_error,
                           return_value=inspect_result):
            self.runtime._update_status()

    @patch_runtime('_error_occurred')
    @patch_runtime('_stopped')
    def test_docker_api_error(self, stopped, error_occurred):
        error = APIError("error")
        self._update_status(inspect_error=error)
        stopped.assert_not_called()
        error_occurred.assert_called_once_with(
            error, "Error inspecting container.")

    @patch_runtime('_error_occurred')
    @patch_runtime('_stopped')
    def test_container_running(self, stopped, error_occurred):
        self._update_status(inspect_result=("running", 0))
        stopped.assert_not_called()
        error_occurred.assert_not_called()

    @patch_runtime('_error_occurred')
    @patch_runtime('_stopped')
    def test_container_exited_ok(self, stopped, error_occurred):
        self._update_status(inspect_result=("exited", 0))
        stopped.assert_called_once()
        error_occurred.assert_not_called()

    @patch_runtime('_error_occurred')
    @patch_runtime('_stopped')
    def test_container_exited_error(self, stopped, error_occurred):
        self._update_status(inspect_result=("exited", -1234))
        stopped.assert_not_called()
        error_occurred.assert_called_once_with(
            None, "Container stopped with exit code -1234.")

    @patch_runtime('_error_occurred')
    @patch_runtime('_stopped')
    def test_container_dead(self, stopped, error_occurred):
        self._update_status(inspect_result=("dead", -1234))
        stopped.assert_not_called()
        error_occurred.assert_called_once_with(
            None, "Container stopped with exit code -1234.")

    @patch_runtime('_error_occurred')
    @patch_runtime('_stopped')
    def test_container_unexpected_status(self, stopped, error_occurred):
        self._update_status(inspect_result=("(╯°□°)╯︵ ┻━┻", 0))
        stopped.assert_not_called()
        error_occurred.assert_called_once_with(
            None, "Unexpected container status: '(╯°□°)╯︵ ┻━┻'.")


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
        self.runtime._set_status(RuntimeStatus.RUNNING)
        update_status.side_effect = \
            lambda: self.runtime._set_status(RuntimeStatus.STOPPED)

        self.runtime._update_status_loop()
        update_status.assert_called_once()
        sleep.assert_called_once_with(DockerCPURuntime.STATUS_UPDATE_INTERVAL)


class TestPrepare(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.prepare,
            valid_statuses={RuntimeStatus.CREATED})

    def test_create_error(self):
        error = APIError("test")
        self.client.create_container_from_config.side_effect = error
        prepared = self._patch_runtime_async('_prepared')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertIsNone(self.runtime._stdin_socket)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_not_called()
            prepared.assert_not_called()
            error_occurred.assert_called_once_with(
                error, "Creating container failed.")

        deferred.addCallback(_check)
        return deferred

    def test_invalid_container_id(self):
        self.client.create_container_from_config.return_value = {"Id": None}
        prepared = self._patch_runtime_async('_prepared')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, AssertionError)

        def _check(_):
            self.assertIsNone(self.runtime._stdin_socket)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_not_called()
            prepared.assert_not_called()
            error_occurred.assert_called_once_with(
                ANY, "Creating container failed.")

        deferred.addCallback(_check)
        return deferred

    def test_attach_socket_error(self):
        self.client.create_container_from_config.return_value = {
            "Id": "Id",
            "Warnings": None
        }
        error = APIError("test")
        self.client.attach_socket.side_effect = error
        prepared = self._patch_runtime_async('_prepared')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertIsNone(self.runtime._stdin_socket)
            self.assertEqual(self.runtime._container_id, "Id")
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_called_once_with(
                "Id", params={"stdin": True, "stream": True})
            prepared.assert_not_called()
            error_occurred.assert_called_once_with(
                error, "Creating container failed.")

        deferred.addCallback(_check)
        return deferred

    def test_warnings(self):
        self.client.create_container_from_config.return_value = {
            "Id": "Id",
            "Warnings": ["foo", "bar"]
        }
        input_socket = self._patch_async('InputSocket')
        prepared = self._patch_runtime_async('_prepared')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)

        def _check(_):
            self.assertEqual(
                self.runtime._stdin_socket,
                input_socket.return_value)
            self.assertEqual(self.runtime._container_id, "Id")
            input_socket.assert_called_once_with(
                self.client.attach_socket.return_value)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_called_once_with(
                "Id", params={"stdin": True, "stream": True})

            warning_calls = self.logger.warning.call_args_list
            self.assertEqual(len(warning_calls), 2)
            self.assertIn("foo", warning_calls[0][0])
            self.assertIn("bar", warning_calls[1][0])

            prepared.assert_called_once()
            error_occurred.assert_not_called()

        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.client.create_container_from_config.return_value = {
            "Id": "Id",
            "Warnings": None
        }
        input_socket = self._patch_async('InputSocket')
        prepared = self._patch_runtime_async('_prepared')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.prepare()
        self.assertEqual(self.runtime.status(), RuntimeStatus.PREPARING)

        def _check(_):
            self.assertEqual(
                self.runtime._stdin_socket,
                input_socket.return_value)
            self.assertEqual(self.runtime._container_id, "Id")
            input_socket.assert_called_once_with(
                self.client.attach_socket.return_value)
            self.client.create_container_from_config.assert_called_once_with(
                self.container_config)
            self.client.attach_socket.assert_called_once_with(
                "Id", params={"stdin": True, "stream": True})
            self.logger.warning.assert_not_called()
            prepared.assert_called_once()
            error_occurred.assert_not_called()

        deferred.addCallback(_check)
        return deferred


class TestCleanup(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.clean_up,
            valid_statuses={RuntimeStatus.STOPPED, RuntimeStatus.FAILURE})

    def test_client_error(self):
        self.runtime._set_status(RuntimeStatus.STOPPED)
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=InputSocket)
        error = APIError("test")
        self.client.remove_container.side_effect = error
        torn_down = self._patch_runtime_async('_torn_down')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.clean_up()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.client.remove_container.assert_called_once_with("Id")
            self.runtime._stdin_socket.close.assert_called_once()
            torn_down.assert_not_called()
            error_occurred.assert_called_once_with(
                error, "Failed to remove container 'Id'.")

        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.runtime._set_status(RuntimeStatus.STOPPED)
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=InputSocket)
        torn_down = self._patch_runtime_async('_torn_down')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.clean_up()
        self.assertEqual(self.runtime.status(), RuntimeStatus.CLEANING_UP)

        def _check(_):
            self.client.remove_container.assert_called_once_with("Id")
            self.runtime._stdin_socket.close.assert_called_once()
            torn_down.assert_called_once()
            error_occurred.assert_not_called()

        deferred.addCallback(_check)
        return deferred


class TestStart(TestDockerCPURuntime):

    def setUp(self):
        super().setUp()
        self.update_status_loop = \
            self._patch_runtime_async('_update_status_loop')

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.start,
            valid_statuses={RuntimeStatus.PREPARED})

    def test_client_error(self):
        self.runtime._set_status(RuntimeStatus.PREPARED)
        self.runtime._container_id = "Id"
        error = APIError("test")
        self.client.start.side_effect = error
        started = self._patch_runtime_async('_started')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.start()
        self.assertEqual(self.runtime.status(), RuntimeStatus.STARTING)
        deferred = self.assertFailure(deferred, APIError)

        def _check(_):
            self.assertIsNone(self.runtime._status_update_thread)
            self.client.start.assert_called_once_with("Id")
            self.update_status_loop.assert_not_called()
            started.assert_not_called()
            error_occurred.assert_called_once_with(
                error, "Starting container 'Id' failed.")

        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.runtime._set_status(RuntimeStatus.PREPARED)
        self.runtime._container_id = "Id"
        started = self._patch_runtime_async('_started')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.start()
        self.assertEqual(self.runtime.status(), RuntimeStatus.STARTING)

        def _check(_):
            self.client.start.assert_called_once_with("Id")
            started.assert_called_once()
            error_occurred.assert_not_called()

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
        self.runtime._set_status(RuntimeStatus.RUNNING)
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=InputSocket)
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = False
        error = APIError("test")
        self.client.stop.side_effect = error
        stopped = self._patch_runtime_async('_stopped')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.assertFailure(self.runtime.stop(), APIError)

        def _check(_):
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.runtime._stdin_socket.close.assert_called_once()
            stopped.assert_not_called()
            error_occurred.assert_called_once_with(
                error, "Stopping container 'Id' failed.")

        deferred.addCallback(_check)
        return deferred

    def test_failed_to_join_status_update_thread(self):
        self.runtime._set_status(RuntimeStatus.RUNNING)
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=InputSocket)
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = True
        stopped = self._patch_runtime_async('_stopped')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.stop()

        def _check(_):
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.runtime._stdin_socket.close.assert_called_once()
            self.logger.warning.assert_called_once()
            stopped.assert_called_once()
            error_occurred.assert_not_called()

        deferred.addCallback(_check)
        return deferred

    def test_ok(self):
        self.runtime._set_status(RuntimeStatus.RUNNING)
        self.runtime._container_id = "Id"
        self.runtime._stdin_socket = Mock(spec=InputSocket)
        self.runtime._status_update_thread = Mock(spec=Thread)
        self.runtime._status_update_thread.is_alive.return_value = False
        stopped = self._patch_runtime_async('_stopped')
        error_occurred = self._patch_runtime_async('_error_occurred')

        deferred = self.runtime.stop()

        def _check(_):
            self.client.stop.assert_called_once_with("Id")
            self.runtime._status_update_thread.join.assert_called_once()
            self.runtime._stdin_socket.close.assert_called_once()
            self.logger.warning.assert_not_called()
            stopped.assert_called_once()
            error_occurred.assert_not_called()

        deferred.addCallback(_check)
        return deferred


class TestStdin(TestDockerCPURuntime):

    def test_invalid_status(self):
        self._generic_test_invalid_status(
            method=self.runtime.stdin,
            valid_statuses={
                RuntimeStatus.PREPARED,
                RuntimeStatus.STARTING,
                RuntimeStatus.RUNNING}
        )

    def test_ok(self):
        self.runtime._set_status(RuntimeStatus.RUNNING)
        sock = Mock(spec=InputSocket)
        self.runtime._stdin_socket = sock

        result = self.runtime.stdin(encoding="utf-8")

        self.assertIsInstance(result, DockerInput)
        self.assertEqual(result._sock, sock)
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
        self.runtime._set_status(RuntimeStatus.RUNNING)

        result = self.runtime._get_output(stdout=True, encoding="utf-8")

        get_raw_output.assert_called_once_with(stdout=True, stream=True)
        update_status.assert_called_once()
        self.assertIsInstance(result, DockerOutput)
        self.assertEqual(result._raw_output, get_raw_output.return_value)
        self.assertEqual(result._encoding, "utf-8")

    @patch_runtime('_update_status')
    @patch_runtime('_get_raw_output')
    def test_stopped(self, get_raw_output, update_status):
        self.runtime._set_status(RuntimeStatus.STOPPED)

        result = self.runtime._get_output(stdout=True, encoding="utf-8")

        get_raw_output.assert_called_once_with(stdout=True, stream=False)
        update_status.assert_called_once()
        self.assertIsInstance(result, DockerOutput)
        self.assertEqual(result._raw_output, get_raw_output.return_value)
        self.assertEqual(result._encoding, "utf-8")

    @patch_runtime('_update_status')
    @patch_runtime('_get_raw_output')
    def test_stopped_in_the_meantime(self, get_raw_output, update_status):
        self.runtime._set_status(RuntimeStatus.RUNNING)
        update_status.side_effect = \
            lambda: self.runtime._set_status(RuntimeStatus.STOPPED)
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

    @patch_runtime('_error_occurred')
    def test_client_error(self, error_occurred):
        error = APIError("test")
        self.client.attach.side_effect = error
        result = self.runtime._get_raw_output(stdout=True)
        self.assertEqual(result, [])
        error_occurred.assert_called_once_with(
            error, "Error attaching to container's output.", set_status=False)

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
