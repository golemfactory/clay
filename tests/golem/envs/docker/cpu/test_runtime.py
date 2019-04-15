from threading import RLock
from unittest.mock import Mock, patch as _patch

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

    @patch('local_client')
    def setUp(self, local_client) -> None:
        payload = DockerPayload(
            image='repo/img',
            tag='1.0',
            args=[],
            binds=[],
            env={}
        )
        self.runtime = DockerCPURuntime(payload, {})
        # RLock enables us to check whether it's owned by the current thread
        self.runtime._status_lock = RLock()

        def _getattribute(obj, item):
            if item == "_status" and not self.runtime._status_lock._is_owned():
                self.fail("Status read without lock")
            return object.__getattribute__(obj, item)

        def _setattr(obj, name, value):
            if name == "_status" and not self.runtime._status_lock._is_owned():
                self.fail("Status write without lock")
            return object.__setattr__(obj, name, value)

        get_patch = patch_runtime('__getattribute__', _getattribute)
        set_patch = patch_runtime('__setattr__', _setattr)
        get_patch.start()
        set_patch.start()
        self.addCleanup(get_patch.stop)
        self.addCleanup(set_patch.stop)


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
